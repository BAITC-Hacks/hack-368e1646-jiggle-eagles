#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
fail() { echo "Money Graph setup failed: $1" >&2; exit 1; }
REQUIREMENTS=requirements-money-graph.txt
case "${1-}" in
  '') [[ $# == 0 ]] || fail 'Usage: ./scripts/setup.sh [--test]' ;;
  --test) [[ $# == 1 ]] || fail 'Usage: ./scripts/setup.sh [--test]'; REQUIREMENTS=requirements-money-graph-test.txt ;;
  --help|-h) echo 'Usage: ./scripts/setup.sh [--test] — create/check .venv and install exact package pins.'; exit 0 ;;
  *) fail 'Usage: ./scripts/setup.sh [--test]' ;;
esac
[[ -r .python-version ]] || fail 'Missing .python-version.'
EXPECTED="$(<.python-version)"
[[ "$EXPECTED" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail '.python-version must contain major.minor.patch.'
[[ ! -L .venv ]] || fail '.venv must be a project-local directory, not a symlink.'
if [[ ! -e .venv ]]; then
  MONEY_GRAPH_INTERPRETER="${MONEY_GRAPH_PYTHON-}"
  if [[ -z "$MONEY_GRAPH_INTERPRETER" ]]; then
    for candidate in "python${EXPECTED%.*}" python3; do
      if command -v "$candidate" >/dev/null 2>&1 && [[ "$("$candidate" -I -c 'import platform; print(platform.python_version())')" == "$EXPECTED" ]]; then
        MONEY_GRAPH_INTERPRETER="$candidate"
        break
      fi
    done
    if [[ -z "$MONEY_GRAPH_INTERPRETER" ]] && command -v uv >/dev/null 2>&1; then
      MONEY_GRAPH_INTERPRETER="$(uv python find --system --no-python-downloads "$EXPECTED" 2>/dev/null || true)"
    fi
  fi
  [[ -n "$MONEY_GRAPH_INTERPRETER" ]] || fail "Install Python $EXPECTED (see .python-version), e.g. uv python install $EXPECTED, then rerun. Or set MONEY_GRAPH_PYTHON to that interpreter's path."
  [[ "$("$MONEY_GRAPH_INTERPRETER" -I -c 'import platform; print(platform.python_version())')" == "$EXPECTED" ]] || fail "Selected interpreter must be Python $EXPECTED."
  "$MONEY_GRAPH_INTERPRETER" -I -m venv .venv
fi
[[ -x .venv/bin/python ]] || fail 'Existing .venv is incomplete. Move it aside, then rerun; it was not replaced.'
.venv/bin/python -I scripts/check_environment.py --runtime-only
# Require a virtual environment even if a user's pip configuration says otherwise.
.venv/bin/python -I -m pip --isolated --require-virtualenv install --disable-pip-version-check -r "$REQUIREMENTS"
.venv/bin/python -I -m pip --isolated check
.venv/bin/python -I scripts/check_environment.py
echo 'Money Graph is ready. Launch: ./scripts/money-graph.sh --serve'
if [[ "$REQUIREMENTS" == requirements-money-graph-test.txt ]]; then
  echo 'Browser tests also need Chromium: .venv/bin/python -m playwright install chromium'
fi
