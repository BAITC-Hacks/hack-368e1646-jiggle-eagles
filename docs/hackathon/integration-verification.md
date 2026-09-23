# Integration and launch verification

Money Graph is the implemented Python dashboard. The Node/React connectivity starter remains a separate application. Feature acceptance and source requirements are mapped in [requirements](requirements.md); the [README](../../README.md) describes supported setup, launch and test commands.

## Reproduce checks

Use the interpreter pinned in [`.python-version`](../../.python-version), then run from the repository root:

```bash
./scripts/setup.sh --test
.venv/bin/python -m playwright install chromium
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m unittest discover -s tests -p 'browser_*.py' -v
```

On Linux, browser system libraries may also be needed; CI uses `playwright install --with-deps chromium`. Normal tests generate synthetic Parquet and use the real local server. Official-data browser acceptance is separately opt-in via `MONEY_GRAPH_TEST_DATA`, as documented in the README. Tests never need AI credentials or paid services.

Setup regression tests cover fresh environment creation, reuse without deletion, interpreter/dependency mismatches, missing packages, rejection of global/shared environments, paths containing spaces, argument forwarding and ignoring ambient Python import paths. They use disposable directories and do not download application packages.

The launch rehearsal should start `./scripts/money-graph.sh --serve --data /path/to/synthetic/input --out /path/to/separate/output` on a free local port, load the page, inspect/export the results, and stop with Ctrl+C. Use separate output directories for concurrent servers. A fresh setup rehearsal must use a new `.venv`; copying an existing environment is not a clean install.

## Node starter checks

```bash
source "$HOME/.nvm/nvm.sh" # if nvm is not already loaded
nvm use
npm ci                   # only when dependencies are not installed
npm run typecheck
npm test
npm run build
```

The starter uses the runtime pinned in [`.nvmrc`](../../.nvmrc). Its `npm start`, development launcher and Docker image do not serve Money Graph. Node tests use mocked AI transport and require loopback sockets.

## CI and verification limits

The [workflow](../../.github/workflows/jiggles-ci.yml) now defines separate Money Graph and legacy Node jobs. Money Graph reads `.python-version`, runs the same isolated setup as developers, installs Chromium, and runs Python/setup/HTTP tests plus the real browser journey. It uses synthetic inputs regardless of the tracked reference dataset.

Local checks are not evidence of a successful remote Actions run. Remote CI for the final revision, an independent second-machine rehearsal, Docker execution and a live organizer presentation remain unverified. No push or public deployment is part of this setup change. The existing reference Parquet files under `docs/my-docs/data/` remain tracked; ignored working copies and outputs under `data/private/` do not change that fact.
