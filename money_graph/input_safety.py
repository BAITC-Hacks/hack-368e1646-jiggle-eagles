"""Resource-bounded Parquet ingestion for the local dashboard and CLI.

File bytes alone do not bound Parquet decoding. Check all input metadata first,
project only contract columns, and retain string dictionaries until their values
have been checked. These ceilings suit local investigation; they are not a native
parser sandbox or a guarantee of a calculation's wall-clock duration.
"""
from contextlib import ExitStack
from pathlib import Path
import hashlib
import os
import stat

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_DECODED_BYTES = 64 * 1024 * 1024
MAX_FOOTER_BYTES = 1024 * 1024
MAX_ROW_GROUPS = 1024
MAX_COLUMNS = 64
MAX_DATE_CHARACTERS = 64  # Includes existing ISO timestamps and timezone errors.
BATCH_ROWS = 8192
ROW_LIMITS = {'nodes': 10_000, 'edges': 50_000, 'transactions': 250_000}
COLUMNS = {
    'nodes': ('gid', 'depth', 'is_seed'),
    'edges': ('src', 'dst', 'sum_kzt', 'n_tx', 'depth'),
    'transactions': ('src', 'dst', 'date', 'sum_kzt'),
}


class InputSafetyError(ValueError):
    """Safe message descriptor; the pipeline translates it to ValidationError."""

    def __init__(self, key: str, **params: object):
        self.key = key
        self.params = params
        super().__init__(key)


def _limit(condition: bool, name: str) -> None:
    if not condition:
        raise InputSafetyError('validation.resourceLimit', name=name)


def _open_input(stack: ExitStack, data_dir: Path, name: str):
    # Nonblocking open avoids hanging on a FIFO passed to the CLI.
    descriptor = os.open(data_dir / f'{name}.parquet', os.O_RDONLY | os.O_NONBLOCK)
    source = stack.enter_context(os.fdopen(descriptor, 'rb'))
    info = os.fstat(source.fileno())
    _limit(stat.S_ISREG(info.st_mode), name)
    return source, info.st_size


def hash_inputs(data_dir: Path) -> dict[str, str]:
    """Bound hashing too: it precedes decoding and must not read huge CLI files."""
    hashes = {}
    total_stored = total_read = 0
    with ExitStack() as stack:
        sources = []
        for name in COLUMNS:
            try:
                source, size = _open_input(stack, data_dir, name)
                total_stored += size
                _limit(total_stored <= MAX_INPUT_BYTES, name)
                sources.append((name, source))
            except OSError as error:
                raise InputSafetyError('validation.parquet', name=f'{name}.parquet') from error
        for name, source in sources:
            digest = hashlib.sha256()
            try:
                while chunk := source.read(1024 * 1024):
                    total_read += len(chunk)
                    _limit(total_read <= MAX_INPUT_BYTES, name)
                    digest.update(chunk)
            except OSError as error:
                raise InputSafetyError('validation.parquet', name=f'{name}.parquet') from error
            hashes[f'{name}.parquet'] = digest.hexdigest()
    return hashes


def _schema(reader: pq.ParquetFile, name: str) -> int:
    """Return a conservative decoded-row estimate without reading data pages."""
    schema = reader.schema_arrow
    if len(set(schema.names)) != len(schema.names) or not set(COLUMNS[name]) <= set(schema.names):
        raise InputSafetyError('validation.columns', name=name)
    row_bytes = 0
    for column in COLUMNS[name]:
        dtype = schema.field(column).type
        if pa.types.is_null(dtype):
            if reader.metadata.num_rows:
                raise InputSafetyError('validation.null', name=name)
            # Empty transaction date columns may have Arrow's null type.
            if column == 'date':
                continue
        if column in {'gid', 'src', 'dst', 'depth', 'n_tx'}:
            if not pa.types.is_integer(dtype):
                raise InputSafetyError('validation.integer', name=name, col=column)
        elif column == 'sum_kzt':
            if not (pa.types.is_integer(dtype) or pa.types.is_floating(dtype)):
                raise InputSafetyError('validation.numeric', name=name)
        elif column == 'is_seed':
            if not pa.types.is_boolean(dtype):
                raise InputSafetyError('validation.boolean')
        else:
            value_type = dtype.value_type if pa.types.is_dictionary(dtype) else dtype
            if pa.types.is_string(value_type) or pa.types.is_large_string(value_type):
                # Up to four UTF-8 bytes per character plus offsets/null bitmap.
                row_bytes += MAX_DATE_CHARACTERS * 4 + 9
                continue
            if not (pa.types.is_date(value_type) or pa.types.is_timestamp(value_type)):
                raise InputSafetyError('validation.date')
        row_bytes += 9  # Fixed-width value and conservative null-bitmap allowance.
    return row_bytes


def _preflight(reader: pq.ParquetFile, name: str) -> int:
    metadata = reader.metadata
    _limit(0 <= metadata.num_rows <= ROW_LIMITS[name], name)
    _limit(metadata.num_row_groups <= MAX_ROW_GROUPS and metadata.num_columns <= MAX_COLUMNS, name)
    estimate = _schema(reader, name) * metadata.num_rows
    page_bytes = 0
    row_count = 0
    for group_index in range(metadata.num_row_groups):
        group = metadata.row_group(group_index)
        row_count += group.num_rows
        for column_index in range(group.num_columns):
            column = group.column(column_index)
            if column.path_in_schema in COLUMNS[name]:
                _limit(column.total_uncompressed_size >= 0 and not column.file_path, name)
                page_bytes += column.total_uncompressed_size
                _limit(page_bytes <= MAX_DECODED_BYTES, name)
    _limit(row_count == metadata.num_rows, name)
    return max(estimate, page_bytes)


def _date_strings(batch: pa.RecordBatch) -> None:
    column = batch.column(batch.schema.get_field_index('date'))
    values = column.dictionary if pa.types.is_dictionary(column.type) else column
    if pa.types.is_string(values.type) or pa.types.is_large_string(values.type):
        maximum = pc.max(pc.utf8_length(values)).as_py()
        _limit(maximum is None or maximum <= MAX_DATE_CHARACTERS, 'transactions')


def read_inputs(data_dir: Path) -> list[pd.DataFrame]:
    """Read the three named files, checking all metadata before decoding any.

    Embedded pandas metadata is ignored: the input contract is the physical
    columns, not attacker-supplied conversion/index metadata. Existing semantic
    validation still checks nulls, int64 range, dates, amounts, and reconciliation.
    """
    readers = []
    total_stored = total_estimate = total_decoded = 0
    with ExitStack() as stack:
        for name in COLUMNS:
            try:
                source, size = _open_input(stack, data_dir, name)
                total_stored += size
                _limit(total_stored <= MAX_INPUT_BYTES, name)
                if size < 12 or source.read(4) != b'PAR1':
                    raise InputSafetyError('validation.parquet', name=f'{name}.parquet')
                source.seek(-8, os.SEEK_END)
                footer = source.read(8)
                footer_size = int.from_bytes(footer[:4], 'little')
                if footer[4:] != b'PAR1' or not 0 < footer_size <= size - 12:
                    raise InputSafetyError('validation.parquet', name=f'{name}.parquet')
                _limit(footer_size <= MAX_FOOTER_BYTES, name)
                source.seek(0)
                options = dict(pre_buffer=False,
                    thrift_string_size_limit=MAX_FOOTER_BYTES,
                    thrift_container_size_limit=10_000, arrow_extensions_enabled=False,
                )
                reader = stack.enter_context(pq.ParquetFile(source, **options))
                total_estimate += _preflight(reader, name)
                _limit(total_estimate <= MAX_DECODED_BYTES, name)
                if name == 'transactions':
                    dtype = reader.schema_arrow.field('date').type
                    value_type = dtype.value_type if pa.types.is_dictionary(dtype) else dtype
                    if pa.types.is_string(value_type) or pa.types.is_large_string(value_type):
                        # Validate the schema before looking up a physical date
                        # column: malformed nested/missing fields have no such
                        # column. Reuse metadata without decoding any pages.
                        reader = stack.enter_context(pq.ParquetFile(
                            source, metadata=reader.metadata, read_dictionary=['date'], **options))
                readers.append((name, reader))
            except InputSafetyError:
                raise
            except (ValueError, OSError, pa.ArrowException) as error:
                raise InputSafetyError('validation.parquet', name=f'{name}.parquet') from error

        frames = []
        for name, reader in readers:
            try:
                batches = []
                rows = 0
                for batch in reader.iter_batches(batch_size=BATCH_ROWS, columns=list(COLUMNS[name]),
                                                  use_threads=False, use_pandas_metadata=False):
                    rows += batch.num_rows
                    total_decoded += batch.nbytes
                    _limit(rows <= ROW_LIMITS[name] and total_decoded <= MAX_DECODED_BYTES, name)
                    if name == 'transactions':
                        _date_strings(batch)
                    batches.append(batch)
                _limit(rows == reader.metadata.num_rows, name)
                schema = pa.schema([reader.schema_arrow.field(column) for column in COLUMNS[name]])
                table = pa.Table.from_batches(batches, schema=schema)
                frames.append(table.to_pandas(ignore_metadata=True))
            except InputSafetyError:
                raise
            except (ValueError, OSError, pa.ArrowException) as error:
                raise InputSafetyError('validation.parquet', name=f'{name}.parquet') from error
    return frames
