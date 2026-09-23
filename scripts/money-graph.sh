#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'First run: ./scripts/setup.sh (uses the Python pin in .python-version).' >&2
  exit 1
fi
.venv/bin/python -I scripts/check_environment.py
for argument in "$@"; do
  if [[ "$argument" == --serve ]]; then
    echo 'Keep this terminal open while using Money Graph. Ctrl+C stops the server.' >&2
    echo 'Wait for the Dashboard URL below before opening your browser.' >&2
    break
  fi
done
# Ignore ambient Python paths/user packages, while keeping the repository importable.
exec .venv/bin/python -E -s -m money_graph "$@"
