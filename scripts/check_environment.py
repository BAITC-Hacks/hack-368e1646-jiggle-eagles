"""Check the project interpreter and exact runtime pins without importing the app."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re
import sys


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    try:
        expected = (root / '.python-version').read_text().strip()
        if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', expected):
            raise ValueError('.python-version must contain an exact major.minor.patch version.')
        actual = '.'.join(map(str, sys.version_info[:3]))
        if actual != expected:
            raise ValueError(f'Python {expected} is required by .python-version; found {actual}. '
                             'Move the old .venv aside and rerun ./scripts/setup.sh.')
        environment = root / '.venv'
        if environment.is_symlink() or Path(sys.prefix).resolve() != environment.resolve() or sys.prefix == sys.base_prefix:
            raise ValueError('Use the project-local .venv; external or global environments are not supported.')
        config = dict(line.split('=', 1) for line in (environment / 'pyvenv.cfg').read_text().splitlines() if '=' in line)
        if {key.strip(): value.strip().lower() for key, value in config.items()}.get('include-system-site-packages') != 'false':
            raise ValueError('.venv must exclude system packages. Move it aside and rerun ./scripts/setup.sh.')
        if sys.argv[1:] == ['--runtime-only']:
            return 0
        if sys.argv[1:]:
            raise ValueError('Usage: check_environment.py [--runtime-only]')
        for line in (root / 'requirements-money-graph.txt').read_text().splitlines():
            pin = line.strip()
            if not pin or pin.startswith('#'):
                continue
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)', pin)
            if not match:
                raise ValueError(f'Expected an exact package pin: {pin}')
            name, required = match.groups()
            try:
                installed = version(name)
            except PackageNotFoundError:
                raise ValueError(f'{name} is missing. Run ./scripts/setup.sh.') from None
            if installed != required:
                raise ValueError(f'{name} must be {required}; found {installed}. Run ./scripts/setup.sh.')
    except (OSError, ValueError) as error:
        print(f'Money Graph environment: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
