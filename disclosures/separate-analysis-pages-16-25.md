# Separate analysis pages

Recorded: 2026-09-23 16:25 (Asia/Almaty, UTC+05:00).

Codex implemented the user's separate list/detail page requirement (MG-UI-04). `/analyses` contains upload and saved history; `/analyses/<id>` opens that saved analysis. Direct URLs, reload and Back/Forward follow the requested analysis, including after an upload-only restart. Successful uploads navigate to their own result URL. Missing/damaged analyses display an error without changing retained results. Detail-page downloads carry a revision guard to avoid returning another tab's active export. No calculation, dataset, artifact format, dependency or external service changed.

Changed files: `money_graph/server.py`, `money_graph/static/{app.js,index.html,file-preview.js}`, `tests/{test_money_graph.py,browser_money_graph.py,browser_themes.py}`, `docs/hackathon/{agent-assignments.md,requirements.md}`, `disclosures/README.md` and this entry. Existing design, localization, saved-details and documentation changes were preserved.

Verification:

- `./scripts/setup.sh --test`: passed with the existing exact dependency pins.
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`: 24 passed.
- `.venv/bin/python -m unittest discover -s tests -p 'browser_*.py' -v`: 10 Chromium tests passed, including the new route/reload/restart/history journey and all previous themes, uploads, metadata and localization journeys.
- With `nvm use`: `npm run typecheck`, `npm test` (49 passed) and `npm run build` passed for the retained Node starter.
- `git diff --check`: passed; the Git index is unchanged from the task baseline.
- The idle live server was restarted with `--serve --upload-only` and its previous saved analysis reopened. All five existing output files retained identical SHA-256 hashes.
- The user's selected browser tab still had the old combined page loaded. It was refreshed, then visually verified at `/analyses`, opened at `/analyses/startup` with the list hidden, and returned with browser Back. The list page is left open.

Unresolved implementation issues: none known for MG-UI-04. Changes remain uncommitted; remote CI has not run because no push was requested. The pre-existing server has one active analysis shared across tabs; account/graph and detail-page export revision checks reject stale data, and refreshing a detail URL restores that analysis.
