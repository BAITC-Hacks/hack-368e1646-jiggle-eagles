# Deployment readiness

The app supports a single production origin for the frontend and API. Public hosting, HTTPS, reviewer access and the evaluation availability window are not configured. Docker image/container execution remains unverified.

## Runtime

- Build with the Node.js version pinned in [`.nvmrc`](../../.nvmrc) and its bundled npm. Keep both `frontend/dist/` and `backend/dist/`, plus runtime dependencies.
- Express serves `/`, frontend assets and `/api/*`. The frontend uses relative API URLs. There is no client-side router or catch-all HTML fallback.
- The [Dockerfile](../../Dockerfile) uses a multi-stage build and the non-root `node` user. Maintain its exact source/asset allowlist in [.dockerignore](../../.dockerignore).
- The local launchers run in the foreground; public hosting needs a persistent process manager or container service. Configure HTTPS at the ingress or proxy.

| Variable | Production setting |
| --- | --- |
| `NODE_ENV` | `production` |
| `HOST` | `0.0.0.0` for container/service ingress; `127.0.0.1` for a proxy on the same host |
| `PORT` | Host-assigned port, integer 1–65535; default 3000 |
| `BODY_LIMIT_BYTES` | Integer 1–1048576 bytes; default 16384 |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Server-only settings if generation is used; health/echo needs neither |

Direct npm startup loads the optional root `.env`, with process variables taking precedence. Containers need injected runtime variables. `DOCKER_PORT` controls only the local launcher's published loopback port.

## Build and launch

From the repository root with the pinned runtime active:

```sh
npm ci --include=dev --no-audit --no-fund
npm run typecheck
npm test
npm run build
NODE_ENV=production npm start
```

Configure the host's restart policy around the production start command. For Docker, follow [README](../../README.md#launch-with-docker) and the [pending Docker checks](integration-verification.md#pending-docker-verification); image builds do not run the full test suite.

## Before making the release available

- Confirm the hosting account, submitted revision, reviewer access method, evaluation window and availability owner. Follow the team's authorized publishing process.
- Verify HTTPS, `/`, assets, health, echo and JSON API errors from the reviewer's access path. Health reports process responsiveness only.
- Verify required credentials are available without exposing them in source, frontend assets or logs.
- Configure restart, capacity and monitoring for the evaluation window; check sleep, expiry and quota limits. Record the deployed revision and URL.
