# Money Graph requirements and verification

## Sources and status

Selected task: **Money Graph — HackAlem AI**, Finance track, task owner Freedom. Official title: «Граф денег: восстановление финансовой структуры организованной группы по транзакционной сети».

- **U:** task summary and minimal first-version and v2 implementation requests supplied by the user on September 23, 2026.
- **S:** [Full technical specification](https://docs.google.com/document/d/1JPLU-G6R25Ge2hVaY2J9cqvrx7FGExj87XKwJPaMz3o/edit?usp=sharing), Russian sections 1–10 and scoring table, read September 23, 2026 through its text export.
- **D:** [Dataset README](https://drive.google.com/file/d/1ro-SiY042jv7De0h7tXBDyY8ZKdHz_US/view?usp=sharing), read September 23, 2026. It defines source columns and collection scope; actual Parquet files and organizer starter are now inspected and hashed in [data profile](data-profile.md).
- **L:** user-approved local setup/version isolation, launch clarity, Python CI and documentation cleanup on September 23, 2026.
- **I:** user request to make the project easily localizable with EN, KZ and RU support, September 23, 2026.
- **H:** user request for upload at the top of the general interface and previous analyses below, with a decision on upload identity, followed by editable titles and optional descriptions and separate list/detail pages with their own URLs, September 23, 2026.
- **V:** user-approved Freedom-inspired interface mockups and Light/Dark/System themes, followed by implementation authorization, September 23, 2026.
- **A:** [Repository agreement](../../AGENTS.md), engineering requirements rather than organizer scoring criteria.

The local Python Money Graph pipeline and dashboard are implemented and verified on the supplied data. The original Node health/echo starter remains separately runnable. Codex is the integrator and acceptance/testing owner; exact ownership is in [assignments](agent-assignments.md). The user/team captain owns registration, current event rules, submission and reviewer data access. Source document/archive hashes are recorded in the data profile.

## Mandatory behavior and deliverables

Acceptance procedures below operationalize U/S; they are not additional organizer clauses. Implementation paths and acceptance coverage are mapped below. The README supplies executable commands; local manifests retain run-specific hashes and timings.

| ID | Source and requirement | Acceptance check | Implementation / verification |
| --- | --- | --- | --- |
| MG-01 | U; S §§5, 7, 9: one reproducible local run from raw Parquet to three exports, under five minutes on the supplied data. | From a clean setup, run the documented command with local inputs and no network/AI credentials; time parsing through final CSV writes, require <300 seconds and retain hardware, versions, input hashes, configuration and timing. Repeat with identical inputs/configuration and compare deterministic outputs. | `money_graph/pipeline.py`, `scripts/money-graph.sh`; official runs about 0.3s, repeated CSV/JSON hashes equal; local manifests retain provenance |
| MG-02 | U; S §§5, 7: every node has a role, confidence, cluster, priority and explanation. | Exact input/output `gid` set equality, 2,248 rows on the confirmed official input, one row per node including isolates; permitted role, finite scores in [0,1], valid cluster reference, nonempty evidence of at most 200 characters. | `pipeline.py`; exact 2,248-gid coverage, 19 isolates, score/evidence constraints and schemas checked; `tests/test_money_graph.py` |
| MG-03 | U; S §7: role criteria are formal and explainable. | Document every rule, metric, threshold, overlap/tie rule and score interpretation. For three arbitrary gids, explain assignments from computed evidence within one minute. Test motifs with independently expected metrics and counterexamples. | `pipeline.py:assign_role`, README rule table; synthetic motifs, tie/ambiguity scores, seed and depth-four counterexamples pass; browser exposes per-account rule |
| MG-04 | U; S §§5, 7: group nodes into clusters and describe their structure. | Every node belongs to a reported cluster; verify `n_nodes`, `n_seed`, internal transfer sums, member references and a supported structural hypothesis; include isolates and disconnected components. Record algorithm, parameters and random seed if used. | `pipeline.py:communities`; 88 clusters, complete membership, seed/member counts and internal KZT independently reconciled; parameters in manifest |
| MG-05 | U; S §§5, 7: rank at least 20 priority nodes with explanations. | At least 20 distinct valid gids, contiguous ranks, documented deterministic tie handling, descending priorities in [0,1], roles/scores matching node export, nonempty `why` supported by computed features. | `pipeline.py`; 50 ranked accounts, exact order and export consistency checked; per-term explanations in CSV/UI |
| MG-06 | U; S §§5, 7: show network directions, roles, clusters and search by gid. | On real frontend/backend, search an arbitrary valid gid, inspect incoming/outgoing links, role, cluster and evidence; verify direction/legend and useful missing-ID behavior. Include isolated and boundary nodes. | `server.py`, `static/`; `tests/browser_money_graph.py` passes on fixtures and official data including search, arrows, coloring, navigation, bounded expansion, isolates and boundary |
| MG-07 | U; S §§6, 9: cautious hypotheses, source-only attributes and collection limits. | Explanations avoid accusations; no external enrichment or invented identity/balance fields. A fourth-hop node with no outgoing edges must not be called a confirmed terminal solely for that absence. Surface the 5,000 KZT threshold, incomplete incoming flows and intra-bank scope. | `pipeline.py`, dashboard and README; all 444 depth-four accounts excluded from terminal, warnings visible; no enrichment or complete-balance inference |
| MG-08 | U; S §§9–10: repository and README explaining one-command reproduction, rules, outputs, limitations and scaling to about one million nodes. | Independent clean-machine rehearsal produces all exports without paid services, cloud cluster or GPU training. README matches delivered behavior and contains a scaling discussion, data-access steps and dependency provenance. No hardcoded gid answer lists. | README, pinned Python dependencies and shell entry point; fresh local venv installed and supplied inputs reproduced; an independent second-machine rehearsal remains unperformed |
| MG-09 | U; S §10: architecture diagram. | Diagram accurately traces delivered data → metrics → roles → interface/exports and identifies optional AI boundaries. | [Delivered diagram](../money-graph/architecture.md) and README; Python graph pipeline, CSVs and local viewer match implementation |
| MG-10 | U; S §10: five-minute live demonstration. | Rehearse a live pipeline run, exports, search and substantive explanation of 2–3 nodes within five minutes, including one collection-limit example. | README walkthrough; automated search/explanation journey rehearsed, live organizer presentation remains with the team |
| ENG-01 | A: automated browser test of the main user journey. | Implement and run against real frontend/backend, replacing only external services where necessary; cover MG-06 and API/error behavior. | `tests/browser_money_graph.py`, test-only Playwright pins; real Python HTTP server + Chromium journey passes without mocked services |
| ENG-02 | A: integrated typecheck, tests, build, diff review and final CI. | Use `nvm use` from the repository root, run root checks and verify CI for the final revision. Separate starter checks from graph acceptance. | Existing root typecheck, 49 Node tests and build pass; Python tests/browser acceptance pass; final diff review local, remote CI pending (no push authorized) |
| ENG-03 | L: pinned, isolated local setup; clear launch path; Python CI and accurate setup/data documentation. | A fresh environment uses `.python-version` and exact package pins; wrong runtimes, dependency drift and shared/global environments fail before launch; compatible environments are preserved; launch works from paths with spaces. The documented server command stays available across requests until stopped, supports restart, and reports startup failure without a ready URL. Reviewer instructions explain terminal lifetime and recovery. CI uses the same setup and synthetic Python/browser tests. | `.python-version`, `scripts/setup.sh`, `scripts/check_environment.py`, `scripts/money-graph.sh`, `tests/test_setup.py`, `tests/test_launch.py`, workflow and setup docs; 9 setup regressions, 3 real CLI launch regressions and a fresh local dependency installation pass. Launch coverage includes synthetic inputs, repeated HTTP requests, Ctrl+C/restart, missing inputs and occupied ports. Remote Actions and a second-machine rehearsal remain unverified. |

## Minimal v2 acceptance

| ID | Confirmed user requirement | Implementation and verification |
| --- | --- | --- |
| MG-V2-01 | Dashboard uploads of all three Parquet files, validation errors/status, active replacement only on success. | `server.py`, `__main__.py`, `static/`: 64 MiB local multipart upload, one worker, staged run, locked snapshot publication, retained inputs/outputs. HTTP/browser tests cover empty startup, valid uploads, invalid reconciliation/corrupt Parquet, runtime failure, concurrent rejection and preservation of active data/downloads. |
| MG-V2-02 | Bounded two-hop expansion, links among visible accounts, zoom/pan/reset and a clear node limit. | Deterministic breadth-first selection with a fixed 50-account limit, including the center; original directed induced edges; visible/eligible/omitted counts. HTTP/browser acceptance covers exact IDs, both hop distances, cap, non-center links, reciprocal/self links, isolates and navigation controls. |
| MG-V2-03 | Improved community descriptions with measured fan-in, fan-out or bridging patterns, numbers and caveats. | `pipeline.py:cluster_description`; independently specified motifs/counts/examples, explicit no-pattern fallback, collection caveats in every description. Calculation tests cover fan-in, fan-out, bridging and isolates; existing role/priority formulas remain unchanged. |
| MG-V2-04 | Extend browser acceptance and preserve existing invariants/reproducibility/runtime. | `tests/browser_money_graph.py` runs real local Python HTTP + Chromium with synthetic uploads; existing supplied-data journey remains available. Python tests verify official schemas, precise IDs, complete node coverage and deterministic artifacts; supplied-data repeat runs verify unchanged scoring and <300s processing. |

Dedicated cluster browsing, advanced filters and a transaction viewer are explicitly deferred. No LLM, training, database, authentication or cloud services are introduced.

## Localization acceptance

| ID | Confirmed user requirement | Implementation and verification |
| --- | --- | --- |
| MG-I18N-01 | I: easily maintained English, Kazakh and Russian localization. | `static/locales/{en,kk,ru}.json`, `static/i18n.js`, `static/app.js`, `i18n.py`, `pipeline.py` and `server.py`: keyed text/parameters, EN/KZ/RU selector (`kk` locale for Kazakh), saved preference, browser-language detection, English fallback, locale-aware dates/numbers and translated static/accessibility/dynamic/error/status content. Exact IDs, role keys, calculations and canonical exports are preserved. `tests/test_localization.py` checks catalog parity, placeholders and API descriptors; `tests/browser_money_graph.py` checks real switching without refetch/state loss, storage/fallback, translated empty/error/success states and mobile layout. `file-preview.js` and `tests/browser_file_preview.py` provide and verify a localized launch guide for direct HTML opening (also supports MG-V2-01 startup guidance). |

Language selection affects dashboard presentation; official exports and CLI diagnostics remain canonical English. Translation quality has not received independent native-speaker review. No dependency or external service is introduced.

## General interface acceptance

| ID | Confirmed user requirement | Implementation and verification |
| --- | --- | --- |
| MG-UI-01 | H: upload at the top, previous analyses below, and a clear upload-identity policy. | `server.py`, `static/{index.html,style.css,app.js,i18n.js,locales/*.json}`: newest-first saved history, local timestamps/counts, empty/error states and reopen action. Design decision: each successful upload has a unique UUID; a fingerprint across all three named file hashes labels matching content without merging runs. History survives restart in the same output directory; reopening verifies artifact hashes and atomically restores original results/downloads. `tests/test_money_graph.py` covers distinct IDs, duplicates, ordering, restart, unchanged export bytes, busy/origin/path validation and damaged-file preservation. `tests/browser_money_graph.py` covers the real upload/history/reopen/restart journey, EN/KZ/RU and mobile layout. |
| MG-UI-02 | H: the analysis title and optional description are editable. | `server.py`, `static/{index.html,style.css,app.js,locales/*.json}`: accessible Edit details dialog, required title (1–120 characters), optional multiline description (0–2,000 characters), save/cancel and clearing. Same-origin JSON updates validate types/limits and atomically save metadata separately from calculation artifacts. Existing analyses remain compatible; details persist after reload/restart, and a new CLI startup does not inherit old metadata. HTTP/browser acceptance covers validation, save/cancel, persistence, localized controls, literal text rendering, mobile layout, write failure preservation and unchanged identities/exports. |
| MG-UI-04 | H: the analysis list and analysis details are separate pages. | `/analyses` contains upload/history only; `/analyses/<id>` opens one saved analysis, including `startup`. Root entry canonicalizes to the list. `server.py` serves nested page URLs with root-relative assets; `app.js` handles direct entry, refresh, Back/Forward and upload navigation without resetting a cached graph. Missing/damaged runs show an error and a return path; downloads carry a revision guard to prevent another tab's active run supplying the wrong export. `tests/test_money_graph.py` and `tests/browser_money_graph.py` cover routes, assets, deep links after restart, refresh against a different active run, URL history, preserved zoom, upload transitions, failed opens and revision-checked exports. Existing theme/localization journeys start investigations at the explicit detail URL. |

## Interface design and themes

| ID | Confirmed user requirement | Implementation and verification |
| --- | --- | --- |
| MG-UI-03 | V: implement the approved Freedom-inspired design in light and dark themes. | `static/{index.html,style.css,theme.js,app.js}`, local catalogs and the `/theme.js` static route: compact header, rounded upload/history cards, separate Analyses/Results views, graph before account evidence, persistent Light/Dark/System selector (System by default), immediate OS-following changes and theme-aware SVG. No calculation, API payload, export or dependency changes. Existing history/details work is preserved. Real browser acceptance covers theme persistence/blocked storage, both palettes, graph and form-state preservation without refetch, view navigation, EN/KZ/RU, mobile overflow, focus and the existing upload/search/reopen/export journey. |

## Required CSV schemas

These headers come from S §5. Do not replace them with a custom export contract. Serialization details not defined by the source must be documented before implementation.

| File | Columns in source order | Source constraints |
| --- | --- | --- |
| `nodes_roles.csv` | `gid,role,role_score,cluster_id,priority_score,evidence` | `gid` int64; role string; `role_score` and `priority_score` floats in [0,1]; cluster integer; human-readable `evidence` at most 200 characters; one row per node |
| `clusters.csv` | `cluster_id,n_nodes,n_seed,sum_kzt_internal,top_gids,hypothesis` | One row per cluster; member/seed counts, internal turnover in KZT, leading gids and purpose/structure hypothesis |
| `top_nodes.csv` | `rank,gid,role,priority_score,why` | Ranked list of at least 20 distinct nodes with text justification |

Minimum role dictionary: `consolidator`, `transit`, `distributor`, `terminal`, `coordinator`, `peripheral`. Any extension must be documented. Role confidence is distinct from investigation priority; without labeled roles neither is a measured probability of wrongdoing or calibrated accuracy.

## Evaluation

| Criterion | Points |
| --- | --- |
| Task completion and functionality | 25 |
| Technical implementation | 25 |
| README and reproducibility | 25 |
| Practical value | 15 |
| Originality and development potential | 10 |

## Decisions and remaining limits

- The actual data contract, archive/starter hashes, float tolerance and component reconciliation are in [data profile](data-profile.md).
- The [README](../../README.md) documents adopted rules, confidence, priority, deterministic ordering, exact-ID CSV/JSON serialization and community parameters. Requirements files pin runtime/test versions; [disclosures](../../disclosures/README.md) identify sources and licenses.
- The user requested a small local version: no application LLM, model training, database, authentication or cloud dependency. Day-level temporal matching is implemented under MG-TIME-01; cycle analysis and sensitivity checks are not implemented.
- Local completeness, runtime, deterministic output and browser behavior are verified; role accuracy is unmeasured because ground truth is absent. A separate-machine setup rehearsal, remote CI and the live organizer presentation remain unperformed.
- The user/team captain retains ownership of reviewer data access, current event rules and submission. Working inputs/results use ignored `data/private/`; existing reference Parquet copies under `docs/my-docs/data/` are tracked and were preserved. No push, additional redistribution or public hosting is part of this setup change.


## Temporal transit evidence (MG-TIME-01)

User requirement: distinguish later spending within 1–2 days from earlier spending, prohibit repeated use of amounts, and report same-day ambiguity separately. `money_graph/temporal.py` allocates non-self daily amounts FIFO; `pipeline.py` gates the existing transit rule on matched incoming share >=0.8. The 0.8 gate is an explicit implementation heuristic, not an organizer threshold or a calibrated probability. Other role formulas and priority weights are unchanged. Account JSON and dashboard JSON gain a `temporal` object; official CSV columns are unchanged, with temporal evidence in transit evidence and ranking explanations. The UI exposes matched amounts, dates, same-day ambiguity and the observation-end warning in all three languages.

Acceptance: earlier/same-day/three-day spending cannot establish transit; one/two-day spending can; incoming and outgoing capacity cannot be reused; partial allocations, duplicates, fractions, shuffled rows, self-transfers, isolates and month-end incompleteness are covered by `tests/test_temporal.py`. `tests/browser_temporal.py` checks the real account journey and translated evidence. AML accuracy remains unmeasured.


## Coexisting observed patterns (MG-PATTERN-01)

User requirement: retain one primary role in the mandatory CSV, while the account card shows simultaneous collection, fast-transit and distribution patterns. `pipeline.py:observed_patterns` computes independent descriptors in account/dashboard `patterns`: collection requires incoming peers >=3 and >=2x outgoing; distribution requires outgoing peers >=5 and >=2x incoming; fast transit requires FIFO 1–2-day matched non-self incoming share >=80%. Fast transit as a pattern does not require monthly balance or non-seed status; it describes measured timing even when those role prerequisites fail. All collection/boundary caveats remain. No role, confidence or priority calculation changes from MG-TIME-01; CSV schemas remain exact. EN/RU/KK cards show each matching pattern with numbers or an explicit no-threshold-met state. Tests cover coexisting collection/transit and distribution/transit, seed/monthly-ratio independence, same-day exclusion, numerical evidence and the real browser card.
