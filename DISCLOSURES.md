# Development disclosures

- OpenAI Codex generated, adapted and reviewed code, tests and documentation at the repository owner's request. Repository content, tool results, aggregate dataset profiles and dashboard verification imagery were used as development context. This development assistance is separate from the application's execution; Money Graph performs no LLM calls.
- Money Graph follows the user's brief, the [official specification](https://docs.google.com/document/d/1JPLU-G6R25Ge2hVaY2J9cqvrx7FGExj87XKwJPaMz3o/edit?usp=sharing) and [dataset README](https://drive.google.com/file/d/1ro-SiY042jv7De0h7tXBDyY8ZKdHz_US/view?usp=sharing). The [dataset archive](https://drive.google.com/file/d/1yHdWaSb6gwPAUrqco-KrwR2U_YhzFQFT/view?usp=sharing) and [organizer Python starter](https://drive.google.com/file/d/1EnMGG22jSH7Mvgt396kKRi3bjAobsomN/view?usp=sharing) were downloaded and inspected September 23, 2026. Local bytes and SHA-256 provenance are documented in [data profile](docs/hackathon/data-profile.md).
- `money_graph/pipeline.py` adapts the organizer starter's Parquet loading, directed graph construction, incoming/outgoing metrics and CSV contract. It adds all-node preservation, strict validation, rules, confidence/priority calculations, deterministic clustering and complete exports. The local HTTP/SVG dashboard and tests were created for this iteration. The starter's PageRank dependency and placeholder outputs are not used. No independently licensed proprietary project code was imported.
- Working inputs, downloaded sources, generated account-level exports and test screenshots use ignored `data/private/money-graph/`. Existing reference copies of all three input Parquet files are also tracked under `docs/my-docs/data/` and match the verified input hashes. Setup preserves those files and does not rewrite Git history; the repository must not be described as containing no raw data. The dataset is authorized for hackathon use, not implicitly for redistribution. Unrelated private files were preserved. No external customer enrichment was performed, and no competition data was submitted to the application's optional legacy OpenAI integration.
- Codex also implemented and checked the pinned interpreter setup, startup environment validation, isolated setup regression tests and Python CI, and reconciled launch/data documentation. Dependency versions and existing reference datasets were preserved.
- Codex clarified reviewer terminal-lifetime/readiness instructions and added regression tests that launch the real shell entry point, check repeated HTTP requests, stop/restart the server and verify missing-input/occupied-port failures. These bounded checks do not establish indefinite uptime or replace a second-machine rehearsal.
- The six role formulas, thresholds and investigation weights are documented heuristic design choices, not organizer ground truth or calibrated probabilities. Communities and role descriptions are hypotheses. Correctness and reproducibility checks do not measure AML accuracy.

## Dependencies and technical sources

The Python interpreter is pinned in `.python-version`; exact runtime and test package pins are in `requirements-money-graph.txt` and `requirements-money-graph-test.txt`. pandas and PyArrow handle Parquet; NetworkX handles graph operations; Python's standard library serves the dashboard. There are no external fonts, CDN scripts or UI analytics. Playwright/Chromium are test-only.

| Dependency | License / purpose |
| --- | --- |
| pandas, NetworkX | BSD-3-Clause; data frames and graph algorithms |
| NumPy | BSD-3-Clause plus bundled 0BSD, MIT, Zlib and CC0-1.0 components; arrays |
| PyArrow | Apache-2.0; Parquet reader |
| python-dateutil | Apache-2.0 or BSD-3-Clause; pandas dependency |
| six | MIT; dateutil dependency |
| Playwright | Apache-2.0; browser automation |
| pyee | MIT; Playwright dependency |
| greenlet | MIT and PSF-2.0; Playwright dependency |
| typing_extensions | PSF-2.0; typing support |

Technical references include the official [pandas Parquet reader](https://pandas.pydata.org/docs/reference/api/pandas.read_parquet.html) and [NetworkX Louvain API](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.louvain.louvain_communities.html). The implementation sorts insertion order and fixes seed/parameters; it preserves directed transfers while clustering an undirected projection.

The pre-existing Node/React starter and its optional OpenAI helper remain unchanged. Their dependencies/licenses remain in `package-lock.json`; original technical sources include official Node.js, Vite, Tailwind, Express, Zod, OpenAI SDK and Docker documentation. The legacy OpenAI tests use mocked transport; no live or paid application AI request was made.

## Verification limits

Python calculation/validation/export/HTTP tests, the real Chromium dashboard journey on synthetic and official data, repeated-output comparisons, official CSV acceptance and existing Node typecheck/tests/build were run locally. Loopback networking and browser execution require sandbox permission; no external app services are used in tests. A browser node hit-area defect found by the journey was fixed and the test rerun successfully.

Remote GitHub Actions for these changes, a second-machine clean setup, Docker execution and a live organizer presentation remain unverified. CI now defines Python/setup/HTTP and real browser checks on synthetic fixtures alongside the separate Node job. Its Python action is pinned to an immutable commit and reads the same `.python-version` as local setup; see [actions/setup-python documentation](https://github.com/actions/setup-python). Configuration is not evidence of a successful remote run. No deployment or push was performed by Codex for this implementation.
