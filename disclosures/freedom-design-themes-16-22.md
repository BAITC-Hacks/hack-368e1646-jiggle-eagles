# Freedom-inspired interface and themes

Recorded: 2026-09-23 16:22 (Asia/Almaty, UTC+05:00).

Codex assisted with the user-approved Money Graph interface redesign, Light/Dark/System preferences, translated interface labels, browser acceptance tests, requirement mapping and this disclosure (MG-UI-03). The original upload, saved-history, editable-details, localization, calculations and export behavior were preserved.

Files changed by the design task: `money_graph/static/{index.html,style.css,theme.js,app.js,file-preview.js}`, `money_graph/static/locales/{en,kk,ru}.json`, `money_graph/server.py` (theme asset route only), `tests/{browser_money_graph.py,browser_file_preview.py,browser_themes.py}`, `docs/hackathon/{requirements.md,agent-assignments.md}`, `disclosures/README.md` and this entry. Existing changes in those files were retained. The separate README task changed `README.md`.

## Design attribution

The light palette was sampled from the rendered [Freedom Bank cards page](https://www.bankffin.kz/ru/cards) on September 23, 2026: brand green `#4FB84E`, primary action `#2A8640`, canvas `#F5F6F7`, white surfaces and `#191919` headings. Rounded surfaces and restrained spacing follow the approved mockups. The dark palette is a Money Graph adaptation, not an assertion about Freedom's official dark-theme specification. No Freedom logo or proprietary font was copied into the app; it uses system fonts and local assets.

Theme selection defaults to System, follows operating-system changes in that mode, and persists locally when browser storage is available. CSS tokens also recolor SVG graph elements without resetting selected files, searches, graph position or analysis data. The Analyses and Results views retain all existing functionality. No new dependency, remote service or runtime asset request was added; customer data is not sent to an external design service.

Codex rewrote the English judge-facing README from repository sources and verified its synthetic-data walkthrough; no runtime behavior or dependencies were changed by the documentation task. That separate user-authorized task owned only `README.md`; its work was handed off for integration.

## Verification and remaining limits

- `./scripts/setup.sh --test` passed with the pinned Python environment.
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`: 24 tests passed.
- `.venv/bin/python -m unittest discover -s tests -p 'browser_*.py' -v`: 9 Chromium tests passed, rerun after the final graph-layout adjustment.
- `.venv/bin/python -m unittest discover -s tests -p 'test_localization.py' -v`: 3 localization tests passed after the final catalog additions.
- With `nvm use`, root `npm run typecheck`, `npm test` (49 tests) and `npm run build` passed for the retained Node starter.
- Browser acceptance covers theme persistence, operating-system preference changes, blocked/invalid storage, graph and upload-state preservation without refetch, history/reopen/edit/export flows, English/Kazakh/Russian, keyboard focus and narrow layouts. Rendered light/dark screens were also inspected locally.
- The local server was restarted to load `/theme.js`, then its original active saved analysis was reopened. All five existing saved output files retained identical SHA-256 hashes.
- The README owner reported successful synthetic and official CLI walkthroughs, a browser smoke of its documented journey, local link checks and unchanged artifact bytes on reopen.
- Working changes remain uncommitted; the existing index was preserved. Remote CI, independent second-machine setup and native-speaker translation review remain unverified. No implementation issues remain known for MG-UI-03.
