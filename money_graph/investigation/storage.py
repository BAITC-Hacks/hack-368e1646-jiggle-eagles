"""Atomic local review storage, separate from reproducible calculation exports."""
from pathlib import Path
import re
import tempfile

from .contracts import ReviewError, digest, encode, parse


class ReviewStore:
    def __init__(self, root: Path):
        self.root = root / 'investigations'

    def write(self, kind: str, identifier: str, value: dict) -> None:
        if kind not in {'reviews', 'snapshots', 'briefs'} or not re.fullmatch(r'[0-9a-f]{32}|[0-9a-f]{64}', identifier):
            raise ReviewError('invalid_record')
        directory = self.root / kind
        directory.mkdir(parents=True, exist_ok=True)
        payload = dict(checksum=digest(value), data=value)
        with tempfile.NamedTemporaryFile(dir=directory, prefix='.pending-', delete=False) as temporary:
            staged = Path(temporary.name)
            try:
                temporary.write(encode(payload))
                temporary.flush()
            except Exception:
                staged.unlink(missing_ok=True)
                raise
        try:
            staged.replace(directory / (identifier + '.json'))
        finally:
            staged.unlink(missing_ok=True)

    def read(self, kind: str, identifier: str) -> dict:
        if kind not in {'reviews', 'snapshots', 'briefs'} or not re.fullmatch(r'[0-9a-f]{32}|[0-9a-f]{64}', identifier):
            raise ReviewError('record_missing', 404)
        try:
            record = parse((self.root / kind / (identifier + '.json')).read_bytes())
            if digest(record['data']) != record['checksum']:
                raise ValueError('checksum')
            return record['data']
        except FileNotFoundError as error:
            raise ReviewError('record_missing', 404) from error
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ReviewError('record_damaged', 422) from error

    def list(self, kind: str) -> tuple[list[dict], int]:
        result, damaged = [], 0
        for path in sorted((self.root / kind).glob('*.json')):
            try:
                result.append(self.read(kind, path.stem))
            except ReviewError:
                damaged += 1
        return result, damaged
