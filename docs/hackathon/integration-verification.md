# Integration and launch verification

Release verification is pending. Local automated results and earlier launch observations are listed separately below; repeat release checks for the submitted revision.

## Automated checks

Local checks on **September 23, 2026** used `nvm use` with the Node.js version pinned in [`.nvmrc`](../../.nvmrc) and its bundled npm. Checked state: uncommitted Money Graph documentation and starter-branding changes on `main`, based on `4ba85885830153873eb06b1c370c850044c5caa1`. These results verify the starter and support ENG-02; they do not establish MG-01–MG-10 feature acceptance or a submitted revision.

| Command | Result |
| --- | --- |
| `npm run typecheck` | Passed for both workspaces, backend tests and the frontend API client |
| `npm test` | 49 passed, 0 failed; loopback networking enabled, AI transport mocked |
| `npm run build` | Passed for frontend and backend |
| `bash -n scripts/start.sh scripts/start-docker.sh` | Passed |

The first sandboxed test run passed 31 tests and failed 18 because loopback listening was denied (`EPERM`). The unchanged suite passed all 49 tests when rerun with loopback permission. No assertions were changed; no live AI request was made. Dependencies were already installed; a fresh `npm ci` rehearsal was not repeated.

Documentation checks found all 73 local Markdown links/anchors valid across 16 files, no stale domain references in active documentation/frontend sources, and no whitespace errors in `git diff --check`. The official specification and dataset README were read; the Money Graph archive and organizer starter were not inspected. Raw-data acceptance, runtime benchmarks and CSV validation remain pending.

## Earlier launch observations

These results came from a clean-copy rehearsal with synthetic inputs. They have not been repeated for a release candidate.

| Area | Recorded result |
| --- | --- |
| Native launcher | Locked install, production build and credential-free startup passed from another directory, including a repository path containing spaces |
| Configuration | Missing `.env` created safely; existing contents preserved; process overrides and custom backend-port proxying passed |
| Frontend and API | HTML/assets, health, trimmed echo, validation errors, body limits and JSON 404 passed on one origin |
| Failure handling | Invalid settings, occupied ports and install/build failures returned nonzero status without exposing sensitive values |
| Shutdown | Native Ctrl+C/SIGINT stopped owned processes and released ports |
| Launcher control flow | 33 isolated shell cases passed; these do not verify container behavior |
| Optional AI CLI | Help and missing-flag/configuration paths passed without a live request |
| Docker | Static configuration and prerequisite failures checked; image build/run was blocked by an unavailable daemon |

Occupied-port failure without false readiness or interruption of the existing listener is covered by [server.test.ts](../../backend/test/server.test.ts).

## Repeat native verification

1. Use a clean copy without private configuration, dependencies or build output; retain `.env.example`. Activate the Node.js version pinned in [`.nvmrc`](../../.nvmrc) with `nvm use` and use its bundled npm.
2. Run the absolute path to `scripts/start.sh` from another directory. Follow the [README](../../README.md) API examples and verify the page and assets.
3. Repeat with an existing synthetic `.env` and a custom `PORT`. Check configuration preservation, process overrides and request size limits.
4. Check invalid settings and an occupied test port. Startup must fail without reporting readiness or stopping the existing listener.
5. Stop with Ctrl+C and confirm the launcher's processes and listeners are gone. Check the development proxy with a custom backend port too.

## Pending Docker verification

When `docker info` succeeds, run `scripts/start-docker.sh` from a clean copy and verify:

- Linux image build, filtered build context and absence of credentials/data in image layers.
- Non-root runtime and same-origin frontend/assets/health/echo.
- Runtime configuration, body limits, invalid settings and occupied host-port failures.
- Foreground Ctrl+C shutdown and removal of the container created by the test.

Use only test-owned processes and containers for cleanup. Native and shell-stub results do not establish Docker runtime behavior.

## Other verification gaps

- Live OpenAI access and output quality: AI transport is mocked in normal tests.
- Remote [CI](../../README.md#continuous-integration): no GitHub Actions run verified for a submitted revision.
- Automated browser coverage: no browser-test runner is configured.
- Public hosting and reviewer access: see [deployment readiness](deployment-readiness.md).
- Money Graph functionality (MG-01–MG-10): the Parquet pipeline, role/cluster/ranking calculations, exports, searchable graph and live demo are not implemented or verified. The architecture is a proposed design; map future acceptance evidence in [requirements](requirements.md).
