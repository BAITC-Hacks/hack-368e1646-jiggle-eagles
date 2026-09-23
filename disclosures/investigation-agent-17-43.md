# Optional investigation agent and live evaluation

Recorded: 2026-09-23 17:43 (Asia/Almaty, UTC+05:00).

Codex assisted with implementation, English/Kazakh/Russian interface text, documentation, synthetic fixtures and verification for the user-approved MG-AG-01–07 plan. The same task integrated the separate upload-reliability task's supplied changes. No dependency was added. Changes remain uncommitted; the pre-existing index was preserved. No push or remote deployment was performed.

## Implementation and sources

The Python calculation configuration supplies both formulas and frozen method descriptions. Saved analyses retain parameters, method text and daily directed aggregates. The investigation package separates contracts, immutable evidence, full-graph candidate discovery, read-only tools, Responses transport, the bounded agent loop, persistence, lifecycle and HTTP adapters. `static/review.js` owns the review panel and uses narrow callbacks into the existing graph viewer. Reviews and briefs are saved separately from official calculation exports.

The implementation follows the official [function-calling guide](https://developers.openai.com/api/docs/guides/function-calling), [structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs), and [GPT-5.4 model documentation](https://developers.openai.com/api/docs/models/gpt-5.4). Requests use strict tool/output schemas, backend execution, explicit usage limits, `store: false` and encrypted reasoning items needed for continued Responses calls. Private reasoning is not saved as checks; checks contain executed actions and results. The selected model is pinned to `gpt-5.4-2026-03-05`, with medium reasoning and a default $0.75 review cap. Price estimates use $2.50 input and $15 output per million tokens, conservatively charging cached input at the full input rate. Provider billing remains authoritative.

Only generated synthetic data was submitted in development API calls. Organizer inputs were used for local calculations and reproducibility checks, not sent to OpenAI during these checks. A user-entered credential was moved from the reusable `.env.example` template to ignored `.env`; a scan confirmed its value was absent from Git-visible files. Credentials stay on the backend. Starting a review in the application sends selected evidence from that analysis to OpenAI; core calculations and manual exploration remain local and credential-free.

## Local verification

- `./scripts/setup.sh --test` passed with the existing exact dependency pins.
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`: 55 tests ran, 54 passed. The sole failure belongs to the separate, paused input-security task's unintegrated files: its nested-date schema test expects `validation.date` but receives `validation.columns`. Those files and assertions were left untouched; their loader was not integrated.
- `.venv/bin/python -m unittest discover -s tests -p 'browser_*.py' -v`: all 16 real Chromium journeys passed, including reviews, Findings/Checks/Evidence, graph and zoom restoration, saved follow-up/briefs, cancellation, analysis switching, restart, themes/locales and upload recovery. Focused investigation/localization/browser checks were rerun after later changes.
- With the pinned Node toolchain, `npm run typecheck`, `npm test` (49 tests) and `npm run build` passed for the retained starter.
- Two official-data reproductions produced identical calculation-output hashes and exact required CSV headers, retained all 2,248 nodes and 19 isolates, assigned 88 communities, ranked 50 accounts and saved 4,286 directed daily aggregates. The measured first run took about 0.42 seconds locally.
- Threshold/community replacement tests verify that a new review sees changed parameters and the replacement method while an existing brief, graph evidence and exports retain their original contents. Tests also reject invented references/values/units, retrieve 77 connections across pages, and cover limits, provider failure, late replies and interrupted reviews.

## Live model assessment

The explicitly invoked evaluation uses two hand-checkable synthetic cases: observed onward activity and collection-boundary absence. Reports remain in ignored `data/private/money-graph/`. Scripted providers in normal tests are never substituted for live results.

Initial GPT-5.4 mini trials exposed incomplete output, excessive repeated checks and incorrect qualitative descriptions despite valid structured measurements. These trials led to incremental decisions, bounded follow-up before recording a decision, more precise instructions and the switch to full GPT-5.4. One comparison run then failed in report formatting after model execution; the writer was fixed and exercised with a scripted CLI smoke check before repeating the comparison.

The final full-model comparison used prompt version four and a stricter $0.70 cap per case:

| Case | Result | Examined / found | Time | Estimated cost |
| --- | --- | --- | --- | --- |
| Onward activity | Partial at spending reservation; one investigate and three insufficient-evidence decisions retained | 4 / 6 | 53.568 s | $0.4238075 |
| Collection boundary | Completed; four investigate and one insufficient-evidence decision | 5 / 5 | 62.301 s | $0.4268025 |

The final cases contained no rejected structured findings: cited measurements and units matched retrieved evidence. The agent inspected downstream activity in the onward case and distinguished the actual boundary account from an interior shared recipient in the boundary case. Its recurring-payment interpretations stayed tentative. Suggested follow-up includes obtaining payment-purpose or wider account context that the toolset cannot itself retrieve.

These are two small integration cases, not a measured accuracy benchmark. Prose can still be imprecise, dispositions for similar patterns can differ, and overlapping candidates can produce repetitive suggestions. Exact reference/measurement validation does not prove every qualitative interpretation. Human review remains necessary, including avoiding fund-lineage implications when comparing observed inflow and outflow. No claim of fraud-detection accuracy, calibrated risk or exhaustive investigation is supported.

Recorded estimates across the saved development runs total $1.63340975. Usage from the report-formatting failure was not recovered; reserving that run's entire $0.75 cap gives a conservative combined upper allowance below $2.39. No further live development requests were needed.

Remote CI on a final revision, independent native-speaker review, second-machine setup, Docker execution and the live organizer presentation remain unverified. The unrelated paused security-test failure remains unresolved.
