#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'First run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-money-graph.txt' >&2
  exit 1
fi
exec .venv/bin/python -m money_graph "$@"
