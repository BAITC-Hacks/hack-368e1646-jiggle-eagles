# Local launch and deployment readiness

## Money Graph dashboard

The supported delivery is a local Python dashboard. Follow the [setup instructions](../../README.md#setup): `./scripts/setup.sh`, then `./scripts/money-graph.sh --serve`. The interpreter is pinned in [`.python-version`](../../.python-version); runtime dependencies live in the project `.venv`. There is no Node build, database, `.env`, API key or cloud service requirement.

The server binds to `127.0.0.1:8765` by default. Use `--port` for another local port, `--data` for authorized inputs, and `--out` for a separate results directory. Ctrl+C stops the foreground server. Avoid concurrent analyses against the same output directory.

The existing Dockerfile packages only the older Node starter. Money Graph has no verified container or public hosting configuration. Its loopback restrictions are deliberate; public hosting would require a separate access-control and deployment design. Tracked reference data under `docs/my-docs/data/` must be considered when distributing the repository; see the [data notes](../../README.md#setup).

## Legacy Node starter

The details below apply only to the older starter. It supports a single production origin for its frontend and API. Public hosting, HTTPS, reviewer access and the evaluation availability window are not configured. Docker image/container execution remains unverified.

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

Configure the host's restart policy around the production start command. For Docker, run `./scripts/start-docker.sh` after starting the Docker daemon; image builds do not run the full test suite. Verify non-root execution, loopback publishing, configuration and Ctrl+C cleanup before relying on the container.

## Before making the release available

- Confirm the hosting account, submitted revision, reviewer access method, evaluation window and availability owner. Follow the team's authorized publishing process.
- Verify HTTPS, `/`, assets, health, echo and JSON API errors from the reviewer's access path. Health reports process responsiveness only.
- Verify required credentials are available without exposing them in source, frontend assets or logs.
- Configure restart, capacity and monitoring for the evaluation window; check sleep, expiry and quota limits. Record the deployed revision and URL.
