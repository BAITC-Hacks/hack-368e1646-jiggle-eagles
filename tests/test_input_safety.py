"""Synthetic input-resource regressions; no paid services or private datasets."""
from datetime import date
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from money_graph import input_safety as safety
from money_graph.pipeline import ValidationError, analyze, dashboard_data
from test_money_graph import fixture, write_fixture


class InputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        write_fixture(self.root)

    def assert_rejected_before_decoding(self, key):
        with patch.object(pq.ParquetFile, 'iter_batches', side_effect=AssertionError('decoded too early')):
            with self.assertRaises(safety.InputSafetyError) as caught:
                safety.read_inputs(self.root)
        self.assertEqual(caught.exception.key, key)

    def test_typed_inputs_keep_calculations_exact_ids_and_extra_columns_ignored(self):
        expected = dashboard_data(analyze(*fixture()))
        frames = list(fixture())
        # This unused variable-width column must never be decoded by the reader.
        frames[0]['unneeded'] = 'x' * 100_000
        write_fixture(self.root, frames)
        decoded = safety.read_inputs(self.root)
        self.assertNotIn('unneeded', decoded[0].columns)
        self.assertEqual(dashboard_data(analyze(*decoded)), expected)
        self.assertEqual(int(decoded[0].gid.iloc[0]), 9007199254740993)

    def test_all_files_preflight_before_any_pages_are_read(self):
        frames = list(fixture())
        frames[2] = frames[2].drop(columns='src')
        write_fixture(self.root, frames)
        self.assert_rejected_before_decoding('validation.columns')

    def test_compressed_repeated_rows_exceed_transaction_limit_before_decode(self):
        rows = safety.ROW_LIMITS['transactions'] + 1
        table = pa.table({'src': pa.array([1] * rows, type=pa.int64()),
                          'dst': pa.array([2] * rows, type=pa.int64()),
                          'sum_kzt': pa.array([5000.] * rows),
                          'date': pa.array([date(2026, 7, 1)] * rows)})
        path = self.root / 'transactions.parquet'
        pq.write_table(table, path, compression='zstd')
        self.assertLess(path.stat().st_size, 100_000)
        self.assert_rejected_before_decoding('validation.resourceLimit')

    def test_dictionary_bomb_rejected_without_expanding_strings(self):
        for string_type in (pa.string(), pa.large_string()):
            with self.subTest(string_type=string_type):
                table = pa.table({'src': pa.array([1] * 1024, type=pa.int64()),
                                  'dst': pa.array([2] * 1024, type=pa.int64()),
                                  'sum_kzt': pa.array([5000.] * 1024),
                                  'date': pa.array(['x' * 32768] * 1024, type=string_type)})
                path = self.root / 'transactions.parquet'
                pq.write_table(table, path, compression='zstd')
                self.assertLess(path.stat().st_size, 5000)
                # Plain decoding materializes at least 32 MiB of date strings.
                # Observe the actual array at the validation boundary instead.
                with patch.object(safety, '_date_strings', wraps=safety._date_strings) as checked:
                    with self.assertRaises(safety.InputSafetyError) as caught:
                        safety.read_inputs(self.root)
                self.assertEqual(caught.exception.key, 'validation.resourceLimit')
                batch = checked.call_args.args[0]
                self.assertTrue(pa.types.is_dictionary(batch.column('date').type))
                self.assertLess(batch.nbytes, 100_000)

    def test_strings_preserve_existing_date_semantics(self):
        expected = dashboard_data(analyze(*fixture()))
        for text, error in [('2026-07-01', None),
                            ('2026-08-01', 'validation.dateRange'),
                            ('2026-07-01 12:00:00', 'validation.dayPrecision'),
                            ('2026-07-01T00:00:00+05:00', 'validation.timezone')]:
            with self.subTest(text=text):
                frames = list(fixture())
                frames[2]['date'] = text
                write_fixture(self.root, frames)
                decoded = safety.read_inputs(self.root)
                if error:
                    with self.assertRaises(ValidationError) as caught:
                        analyze(*decoded)
                    self.assertEqual(caught.exception.message['key'], error)
                else:
                    self.assertEqual(dashboard_data(analyze(*decoded)), expected)

    def test_schema_rejects_variable_width_ids_and_amounts_before_decoding(self):
        for index, column, value, error in [
            (0, 'gid', '1' * 32768, 'validation.integer'),
            (1, 'sum_kzt', '5' * 32768, 'validation.numeric'),
            (2, 'date', ['x'] * 1024, 'validation.date'),
        ]:
            with self.subTest(column=column, index=index):
                frames = list(fixture())
                frames[index][column] = pd.Series([value] * len(frames[index]))
                write_fixture(self.root, frames)
                self.assert_rejected_before_decoding(error)

    def test_footer_and_file_bytes_are_bounded_before_arrow(self):
        path = self.root / 'transactions.parquet'
        with path.open('wb') as source:
            source.write(b'PAR1')
            source.seek(safety.MAX_FOOTER_BYTES + 5)
            source.write(struct.pack('<I', safety.MAX_FOOTER_BYTES + 1) + b'PAR1')
        with patch.object(pq.ParquetFile, 'iter_batches', side_effect=AssertionError('unexpected decode')):
            with self.assertRaises(safety.InputSafetyError) as caught:
                safety.read_inputs(self.root)
        self.assertEqual(caught.exception.key, 'validation.resourceLimit')
        with path.open('wb') as source:
            source.truncate(safety.MAX_INPUT_BYTES + 1)
        self.assert_rejected_before_decoding('validation.resourceLimit')

    def test_aggregate_decoded_budget_checked_before_reading_pages(self):
        # Normal individual files fit, but their combined estimate exceeds this
        # deliberately small test budget. No allocation near the real cap occurs.
        with patch.object(safety, 'MAX_DECODED_BYTES', 1000):
            self.assert_rejected_before_decoding('validation.resourceLimit')

    def test_many_small_row_groups_have_a_metadata_limit(self):
        table = pa.table({'gid': range(safety.MAX_ROW_GROUPS + 1),
                          'depth': [1] * (safety.MAX_ROW_GROUPS + 1),
                          'is_seed': [False] * (safety.MAX_ROW_GROUPS + 1)})
        pq.write_table(table, self.root / 'nodes.parquet', row_group_size=1)
        self.assert_rejected_before_decoding('validation.resourceLimit')

    def test_pandas_index_metadata_cannot_load_unselected_column(self):
        frames = list(fixture())
        frames[0].index = pd.Index(['x' * 32768] * len(frames[0]), name='untrusted_index')
        frames[0].to_parquet(self.root / 'nodes.parquet', index=True)
        decoded = safety.read_inputs(self.root)
        self.assertEqual(list(decoded[0].columns), ['gid', 'depth', 'is_seed'])
        self.assertIsInstance(decoded[0].index, pd.RangeIndex)

    def test_hashing_matches_source_bytes_and_obeys_aggregate_size_cap(self):
        expected = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in self.root.glob('*.parquet')}
        self.assertEqual(safety.hash_inputs(self.root), expected)
        total = sum(path.stat().st_size for path in self.root.glob('*.parquet'))
        with patch.object(safety, 'MAX_INPUT_BYTES', total - 1):
            with self.assertRaises(safety.InputSafetyError) as caught:
                safety.hash_inputs(self.root)
            self.assertEqual(caught.exception.key, 'validation.resourceLimit')
            self.assert_rejected_before_decoding('validation.resourceLimit')

    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        path = self.root / 'nodes.parquet'
        path.unlink()
        os.mkfifo(path)
        for reader in (safety.hash_inputs, safety.read_inputs):
            with self.subTest(reader=reader.__name__), self.assertRaises(safety.InputSafetyError) as caught:
                reader(self.root)
            self.assertEqual(caught.exception.key, 'validation.resourceLimit')

    def test_empty_edges_and_transactions_keep_isolated_accounts(self):
        frames = list(fixture())
        frames[1], frames[2] = frames[1].iloc[:0], frames[2].iloc[:0]
        write_fixture(self.root, frames)
        result = analyze(*safety.read_inputs(self.root))
        self.assertEqual(result.profile['nodes'], 30)
        self.assertEqual(result.profile['edges'], 0)
        self.assertEqual(result.profile['transactions'], 0)

    def test_missing_or_duplicate_columns_fail_before_decoding(self):
        frames = list(fixture())
        frames[2] = frames[2].drop(columns='date')
        write_fixture(self.root, frames)
        self.assert_rejected_before_decoding('validation.columns')
        write_fixture(self.root)
        duplicated = pa.Table.from_arrays([pa.array([1]), pa.array([2]), pa.array([0]), pa.array([True])],
                                          names=['gid', 'gid', 'depth', 'is_seed'])
        pq.write_table(duplicated, self.root / 'nodes.parquet')
        self.assert_rejected_before_decoding('validation.columns')


if __name__ == '__main__':
    unittest.main()
