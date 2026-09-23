# HackAlem agent working agreement

## Start and verify

Read this file, any more specific `AGENTS.md`, [README.md](README.md), [DISCLOSURES.md](DISCLOSURES.md), and the task's source requirements before editing. The integrator first records the branch/HEAD, `git status --short`, unstaged diff and staged diff; preserve all existing work and the index. In a shared checkout, other agents use that supplied baseline.

Money Graph is the Python dashboard. Run `./scripts/setup.sh` to create/check its isolated `.venv` and install exact dependency pins. [`.python-version`](.python-version) is the single source of truth for the interpreter; setup and launch enforce it. Use `./scripts/money-graph.sh --serve` to launch. `./scripts/setup.sh --test` also installs browser-test dependencies; install Chromium separately with `.venv/bin/python -m playwright install chromium`.

Python checks: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` and `.venv/bin/python -m unittest discover -s tests -p 'browser_*.py' -v`. Tests use synthetic fixtures by default; HTTP/browser checks require loopback networking. CI runs these separately from the retained Node starter.

The following Node commands and the existing Docker image launch/check the legacy starter, not Money Graph. For that starter, run commands from the repository root with the Node.js version pinned in [`.nvmrc`](.nvmrc) and its bundled npm. `.nvmrc` is the single source of truth for the toolchain; reference it instead of duplicating Node.js or npm version requirements in documentation. Activate it first with `nvm use`; do not assume the shell has it.

| Command | Purpose / verified behavior |
| --- | --- |
| `npm run dev` | Vite on `127.0.0.1:5173`, Express on port 3000 by default; `/api` is proxied to the backend, honoring `PORT`. |
| `npm run typecheck` | Both workspaces plus backend tests and the frontend API client. |
| `npm test` | Node test runner: HTTP/configuration tests and frontend API-client round trip; requires loopback networking. |
| `npm run build` | Type-checks, then builds `frontend/dist/` and `backend/dist/`. |
| `npm start` | Serves the existing production build and API from Express. |

Setup when needed: `npm ci` at the root, using the existing root lockfile. Only the integrator installs dependencies in a shared checkout; `scripts/start.sh` also installs dependencies. Do not install or build concurrently against the same dependency/output directories. There is no configured lint or Node browser-test script; never claim unrun checks.

## Code quality and testing

- Implement only assigned requirements. Keep changes focused, preserve unrelated or staged work, and follow existing conventions. Coordinate shared-file and dependency changes under the ownership rules below.
- Prefer straightforward functions and explicit data flow. Avoid speculative abstractions, duplicate implementations and unused code.
- Keep routes thin: validate input, call feature logic, return a response. Keep business calculations out of UI components and AI prompts.
- Validate external inputs and model outputs at runtime before using them.
- Do not introduce `any`, unsafe casts or suppressed checks merely to make the build pass. Explain unavoidable exceptions.
- Handle errors explicitly. Never swallow errors, return fake success, or silently substitute mock output when a real service fails.
- Keep secrets and sensitive data out of logs and frontend code.
- Comment assumptions, units and non-obvious decisions.

### Automated tests

- Reuse the existing test tools and commands. Coordinate new test tooling and dependencies with the integrator and affected owners.
- Test important calculations, validation, API behavior and failure cases. Avoid tests for trivial implementation details or cosmetic changes.
- Derive expected results from requirements or independently verified examples, not from the implementation being tested.
- Keep normal tests deterministic and credential-free. Mock external AI services; do not make paid requests during tests, startup or health checks.
- Maintain the Money Graph browser journey in `tests/browser_money_graph.py` using the real frontend and backend. Playwright is test-only; replace only external services when necessary. Keep CI coverage aligned with the main user journey.
- Keep live AI checks separate and explicitly invoked. Mocked test success does not establish model quality or live integration readiness.
- Add a focused regression test for significant bugs where practical.
- Never weaken assertions, skip failing tests or change expected results merely to make CI green.
- Prioritize meaningful coverage of mandatory behavior over coverage targets.

## Ownership and coordination

Name **one integrator** and assign each agent an explicit role, task and exact, nonoverlapping file paths in [agent assignments](docs/hackathon/agent-assignments.md) before parallel work. Do not infer ownership from teammate names. These are default ownership boundaries, not permission for multiple agents to edit the same lane:

| Owner | Files / responsibility |
| --- | --- |
| Integrator | Root files/configuration (including `AGENTS.md`, `README.md`, `DISCLOSURES.md`), `scripts/**`, all dependency manifests and lockfiles, `backend/tsconfig*.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`; shared API contracts currently embedded in `backend/src/app.ts` and `frontend/src/api.ts`, plus `backend/test/app.test.ts` and future shared contract/schema files; final integration. |
| Backend agent | Assigned files in `backend/src/**` except `app.ts`, and `backend/test/**` except `app.test.ts`. |
| Frontend agent | `frontend/index.html` and assigned files in `frontend/src/**` except `api.ts`. |
| Docs/domain agent | Assigned files in `docs/money-graph/**` and `docs/hackathon/**`. |

- The feature implementer includes relevant tests with each feature; coordinate tests in shared files with their owner.
- Explicitly assign an acceptance/testing owner to define acceptance criteria from confirmed requirements, independently checked examples and cross-feature verification. This role may be held by the integrator; it does not grant ownership of other agents' files.
- The integrator owns shared configuration, dependencies, integration checks and verification of CI on the final commit. Record pending or unavailable CI as a verification gap; do not push without explicit instruction.
- Unlisted files need an explicit owner. Split a lane into disjoint paths before assigning additional agents. Stop and coordinate before editing another owner's file; handoffs transfer ownership explicitly.
- Agree API-contract and dependency changes with the integrator and affected producers/consumers **before implementation**. Record endpoints, request/response shapes, validation/errors, units/time semantics, dependency/version rationale and acceptance checks. The integrator edits shared contract files and manifests/lockfiles.
- Prefer a separate worktree and branch per agent. Worktrees start from committed state: the integrator must deliberately establish a base containing required work; never assume staged/uncommitted files are copied. Do not commit another person's staged work to create that base without authorization.
- In a shared checkout, **only the integrator performs any Git operations or dependency installation**. Other agents edit owned files and report their file lists; the integrator supplies SHAs/diffs and handles staging, commits and integration. In isolated worktrees, keep Git operations scoped to the assigned branch and coordinate integration.
- Never overwrite/revert unrelated changes, run destructive Git commands (`reset --hard`, `clean`, force-push), or stage broadly (`git add .`, `git add -A`, `git commit -a`). The integrator reviews working and staged diffs separately and stages only explicit owned paths, preserving pre-existing staged hunks. Do not push unless explicitly instructed.

## Evidence, domain and handoff

- Keep routine documentation cleanup and agent execution logs in the conversation. Do not populate repository requirements or assignment templates with these records.
- Map confirmed requirements to implementation and verification in [requirements](docs/hackathon/requirements.md). Do not invent task requirements or dataset semantics. Before graph calculations, read [docs/money-graph/README.md](docs/money-graph/README.md), its methodology, and the actual dataset documentation. Record identifier types, edge direction, amount units, date precision, collection depth, threshold, scope and provenance; block dependent calculations when semantics remain unresolved.
- Treat roles, clusters and investigation priorities as hypotheses, never accusations. Explain role rules, thresholds and ranking contributions. Preserve every supplied node, including isolates. Account for the four-hop boundary, unobserved incoming flows and transfers below 5,000 KZT; observed flows do not establish account balances. Never invent customer attributes or enrich them externally. Core reproduction must run locally without paid services, cloud clusters or GPU training; AI assistance is optional.
- Never expose secrets in code, logs, prompts, screenshots or handoffs, or send unauthorized repository/data content to external services. Use synthetic/local fixtures where possible; keep credentials out of Git.
- Before handoff, inspect the diff and run relevant checks. Every handoff states **changed files, checks performed (commands/results/evidence), and unresolved issues** (explicitly “none” when applicable), plus requirement IDs and commit SHA or uncommitted status. Report checks passed, failed or not run, with reasons. Include proposed disclosure text for the integrator when AI/tools contributed.
- The integrator reviews all handoffs, reruns relevant acceptance checks and root type-check/test/build commands on the integrated result, and records any verification gaps before final delivery.
- A feature is done when integrated and verified against acceptance criteria.
