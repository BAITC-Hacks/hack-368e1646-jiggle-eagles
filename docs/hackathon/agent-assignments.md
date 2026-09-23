# Money Graph implementation ownership

The “Launch the app” task is the integrator and acceptance/testing owner for setup/configuration requirements ENG-02–03. Existing feature implementation and acceptance ownership for MG-01–09 and ENG-01 is unchanged. Only setup changes are included in this task’s commit; unrelated working-tree edits and the existing index are preserved.

Owned implementation paths: `money_graph/__init__.py`, `money_graph/__main__.py`, `money_graph/pipeline.py`, `money_graph/server.py`, `money_graph/static/index.html`, `money_graph/static/style.css`, `money_graph/static/app.js`, `tests/test_money_graph.py`, `tests/browser_money_graph.py`, `requirements-money-graph.txt`, `requirements-money-graph-test.txt`, `scripts/money-graph.sh`, `.gitignore`, `README.md`, `DISCLOSURES.md`.

Owned documentation paths: this file, `docs/hackathon/requirements.md`, `docs/hackathon/data-profile.md`, `docs/money-graph/methodology.md`, `docs/money-graph/architecture.md`, `docs/money-graph/README.md`. Inputs, source archives and generated results are owned under ignored `data/private/money-graph/`. Existing Node/React code, index and unrelated private files are preserved. The user-provided `docs/money-graph/task.md` is read-only.

Setup task exclusive ownership: `.python-version`, `scripts/setup.sh`, `scripts/check_environment.py`, `scripts/money-graph.sh`, `tests/test_setup.py`, `.github/workflows/jiggles-ci.yml`, the introductory comment in `requirements-money-graph.txt`, startup guidance in `AGENTS.md`, `docs/hackathon/deployment-readiness.md` and `docs/hackathon/integration-verification.md`. Shared setup edits in README.md, DISCLOSURES.md, docs/hackathon/requirements.md and this file are staged separately from feature work.

## Agreed local contract

- Python CLI reads the three documented Parquet files, validates before calculating, writes the three official CSV schemas and a deterministic dashboard JSON. A separate run manifest records hashes, versions, hardware and timing.
- Python standard-library HTTP server binds only to `127.0.0.1`. Read-only `GET /api/overview` returns counts, cluster summaries and ranked accounts; `GET /api/account?gid=<exact decimal int64>` returns measured features, role rules, priority contributions and all incident directed edges. IDs are decimal strings in JSON. Invalid queries return 400, missing IDs/routes 404; runtime failures never substitute demo results.
- CSV uses UTF-8, LF, exact decimal int64 IDs, fixed six-decimal scores and JSON arrays of decimal strings for `top_gids`. Amounts are observed KZT; dates have day precision with no timezone. Graph direction is payer → recipient; all supplied nodes are added first.
- pandas and PyArrow load/validate Parquet; NetworkX builds the directed graph and seeded weighted Louvain communities. Exact dependency pins are in the two requirements files; Playwright is test-only. No new Node dependencies, external assets or runtime network services.
- Acceptance: strict schemas and reconciliation; synthetic motifs and boundary counterexamples; all-node coverage including isolates; at least 20 ranked official accounts; byte-identical repeated CSV/JSON output; timed official run below 300 seconds; real HTTP and automated browser journey; existing root typecheck/tests/build. Remote CI remains a gap until a user-authorized push.

- Local setup contract (ENG-03): `.python-version` pins the existing verified interpreter; setup creates or checks `.venv`, installs the unchanged exact requirements and verifies dependencies. Launch validates runtime/package versions without installing anything. CI uses the same setup and separate synthetic Python/browser checks. No application API or data semantics change.
