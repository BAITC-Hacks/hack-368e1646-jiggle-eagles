# Dependencies, licenses and technical sources

Migrated: 2026-09-23 16:08 (Asia/Almaty, UTC+05:00). This records the migration time; the original work times were not recorded.

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
