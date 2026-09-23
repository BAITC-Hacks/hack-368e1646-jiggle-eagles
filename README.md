# hack-368e1646-jiggle-eagles
Hackathon team repository for Jiggle Eagles

## HackAlem

A minimal connectivity test: React + Vite + TypeScript + Tailwind in `frontend/`, Node.js + Express + TypeScript + Zod in `backend/`. See [DISCLOSURES.md](DISCLOSURES.md) for sources and AI assistance.

### Launch locally

Prerequisites: Bash, the Node.js version pinned in [`.nvmrc`](.nvmrc) with its bundled npm, and internet access for the first dependency install. `.nvmrc` is the single source of truth for the toolchain. Use your existing Node version manager if needed (`nvm install && nvm use` from this repository). The launchers never install system software.

From the repository root:

```bash
nvm install   # once: installs the version pinned in .nvmrc
nvm use       # activates the version pinned in .nvmrc
./scripts/start.sh
```

Or from **any** working directory:

```bash
/absolute/path/to/this-repository/scripts/start.sh
```

The script checks Node/npm, creates `.env` only when missing, runs `npm ci --include=dev --no-audit --no-fund` and `npm run build`, then starts Express with `NODE_ENV=production`. Open **http://localhost:3000** and send `Hello, HackAlem!`. The page should display it under “API response.” Express serves both the built frontend and `/api` at this URL. Press **Ctrl+C** to stop. Startup requires no AI credentials or AI service access.

### Launch with Docker

Prerequisites: Bash and a running Docker engine (no host Node/npm required).

```bash
./scripts/start-docker.sh
# Optional alternative host port:
DOCKER_PORT=8080 ./scripts/start-docker.sh
```

An absolute path to the script also works from any directory. It creates `.env` only if missing, builds `hackalem:local`, and runs it in the foreground with `--rm` and an init process. Open **http://localhost:3000** (or your `DOCKER_PORT`). Ctrl+C stops and removes this container. Runtime configuration comes from `.env`; Docker always listens on port 3000 inside the container and publishes only to host loopback. No Compose file is needed.

The launcher reads the Node.js version from `.nvmrc` and passes it as a build argument to all stages of the image, which runs as the non-root `node` user. Its build context allows only exact app build inputs and excludes `.env` and key files. Runtime configuration stays out of build arguments. Add each new source file or asset explicitly to `.dockerignore` when needed by the build. The OpenAI helper is included; the optional TypeScript connectivity CLI is a native development command and is not shipped in the runtime image. Keep credentials out of source code; the connectivity app needs none.

Docker build/run remains unverified because the local daemon is unavailable. After starting your Docker engine, `docker info` must succeed before using the launcher.

### Development and commands

```bash
# With the pinned Node version active, from the repository root:
npm ci
npm run dev        # page: http://localhost:5173; API: http://localhost:3000
npm run typecheck
npm test
npm run build
NODE_ENV=production npm start  # serves the existing production build
npm run openai:check -- --help # help only; makes no request
```

Development uses Vite's `/api` proxy to Express, including a custom backend `PORT`. Vite stays on port 5173 and fails if it is occupied. Ctrl+C stops both development processes. Only the root `package-lock.json` is used. Install dependencies from the repository root.

### Continuous integration

The [CI workflow](.github/workflows/jiggles-ci.yml) runs `npm ci`, `npm run typecheck`, `npm test` and `npm run build` on pushes and pull requests. Its single `ubuntu-latest` job has a 15-minute timeout and uses `.nvmrc` and the root lockfile. Tests use synthetic fixtures, loopback HTTP and mocked AI transport; keep the live `openai:check` command outside CI.

Actions are pinned to exact commits with only `contents: read` permission. Checkout credential persistence and package-manager caching are disabled. The workflow does not deploy or upload artifacts. Remote execution remains unverified; check the run for the submitted revision. Local results and launch procedures are in [integration verification](docs/hackathon/integration-verification.md).

### Configuration

`.env.example` contains safe local defaults and empty optional AI settings. Both launchers copy it to `.env` **only if missing**. Edit `.env` yourself; it is ignored by Git and excluded from the image. Direct npm commands also work without `.env`. Do not shell-source this file. Use simple unquoted `KEY=value` entries or full-line `#` comments compatible with Node and Docker, without shell expansion. Docker rejects bare keys and `export KEY=value` lines without printing their values.

| Variable | Default | Accepted values / purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | `127.0.0.1` or `0.0.0.0`; local backend bind address |
| `PORT` | `3000` | Integer 1–65535; local backend port and Vite proxy target |
| `BODY_LIMIT_BYTES` | `16384` | Integer 1–1048576; maximum JSON request body bytes |
| `DOCKER_PORT` | `3000` | Export to the Docker launcher; published host port (not read from `.env`) |
| `OPENAI_API_KEY` | Empty / absent | Optional server-only key; validated only when `generateText` is called |
| `OPENAI_MODEL` | Empty / absent | Optional Responses model identifier; required only with explicit generation |

For local launches, process environment overrides the root `.env`, e.g. `PORT=4000 ./scripts/start.sh`. Vite and Node use that same file for backend settings; `.env.local` and mode-specific files do not override the backend port. For Docker, edit `.env` for `BODY_LIMIT_BYTES`; the launcher overrides `HOST=0.0.0.0` and `PORT=3000` inside the container. An explicitly empty `DOCKER_PORT` is invalid. Invalid backend settings stop startup with field names and constraints, without printing values. Occupied ports cause failure without announcing readiness; no processes are killed. Change the relevant port or stop its owner yourself.

Keep AI settings on the server; never use a `VITE_` prefix for credentials. Empty, missing or invalid AI settings do not block the health/echo app. The standalone connectivity CLI deliberately reads only explicitly exported process variables, not `.env`.

### Optional AI connectivity check

The server-only `generateText` helper in `backend/src/openai.ts` uses the official `openai@7.21.0` SDK and Responses API. It is not registered on an HTTP route. It caps input at 4,000 trimmed characters and output at 256 tokens (including reasoning), uses a 10-second timeout per attempt and a 15-second total deadline, and permits at most one SDK retry. It returns text and safe duration/model/usage metadata, or a fixed error code/message. It disables SDK logging and response storage (`store: false`); callers must keep prompts, keys and generated text out of logs.

Normal startup, `/api/health`, `npm test`, build and CI never call AI. `npm run openai:check` without the flag exits 2 and makes no request; `--help` exits 0. The live check is separate and may incur cost. It sends only the fixed synthetic prompt `Reply with exactly OK.`, with 16 output tokens and zero retries. It accepts only `gpt-4.1-nano` or `gpt-4.1-nano-2025-04-14`; actual project/model access is unverified.

With an authorized API key, model access and spending limits confirmed, run in Bash using the pinned Node version:

```bash
# Enter the authorized project key at the hidden prompt; do not paste it into a command.
read -r -s -p 'Authorized project API key: ' OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY
OPENAI_MODEL=gpt-4.1-nano npm run openai:check -- --allow-paid-request
unset OPENAI_API_KEY
```

The CLI prints safe metadata only. Missing configuration exits 2; authentication, model access, quota, rate-limit or timeout failures exit 1 with actionable messages. Resolve billing/access failures before another attempt.

### API examples

```bash
curl http://localhost:3000/api/health
# {"status":"ok"}

curl -X POST http://localhost:3000/api/echo \
  -H 'Content-Type: application/json' \
  -d '{"text":"  Hello, HackAlem!  "}'
# {"text":"Hello, HackAlem!"}

curl -X POST http://localhost:3000/api/echo \
  -H 'Content-Type: application/json' -d '{"text":""}'
# HTTP 400:
# {"error":{"code":"VALIDATION_ERROR","message":"Send an object containing only text: a string of 1–1000 characters after trimming.","issues":[{"field":"text","message":"text must contain at least one non-whitespace character."}]}}
```

`text` must be a string, trimmed to 1–1,000 JavaScript string characters; extra fields are rejected. The frontend disables empty submissions and shows loading, results, and API/network errors. Requests time out in the browser after 10 seconds. Content must be uncompressed JSON.

All application errors use `{ "error": { "code": "...", "message": "..." } }`, with optional validation `issues`: 400 `VALIDATION_ERROR` / `INVALID_JSON` / `INVALID_REQUEST`, 413 `PAYLOAD_TOO_LARGE`, 415 `UNSUPPORTED_MEDIA_TYPE`, 404 `NOT_FOUND`, and 500 `INTERNAL_ERROR`. Unknown API paths and methods return JSON, never the frontend HTML.

### Tests and limits

`npm test` uses Node's test runner and actual HTTP requests on ephemeral loopback ports. It covers health, valid and invalid echo inputs, malformed JSON, size limits, media types, missing endpoints, static serving, safe logs, configuration validation, the frontend API client's round trip, and occupied-port startup. AI tests inject mocked transport and prohibit real fetch; importing the CLI does not execute it. `npm run build` also runs type-checks. No automated browser-test runner is configured.

Request logs contain generated IDs, fixed route labels, status codes and durations; they exclude request text, URLs/query strings, headers, environment values and exception details. The optional AI helper has no UI or public endpoint. There is no persistence, database, authentication, rate limiting, queue, agent framework, TLS, deployment or domain-specific workflow. Health reports process responsiveness only. Only `/` is a frontend page; there is no client-side router or catch-all HTML fallback. Public hosting, HTTPS and reviewer access are not configured.

### Working references

- [Hackathon working guide](docs/hackathon/orientation.md): task selection, ownership and delivery.
- [Energy references](docs/energy/README.md): measurement semantics, calculations and validation.
- [Agent agreement](AGENTS.md): development and verification rules.
