#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail() { echo "Launch failed: $1" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || fail 'Docker is required. Install and start it, then rerun this script.'
PORT_TO_PUBLISH="${DOCKER_PORT-3000}"
[[ "$PORT_TO_PUBLISH" =~ ^[0-9]{1,5}$ ]] && (( 10#$PORT_TO_PUBLISH >= 1 && 10#$PORT_TO_PUBLISH <= 65535 )) || {
  fail 'DOCKER_PORT must be an integer from 1 to 65535.'
}
PORT_TO_PUBLISH="$((10#$PORT_TO_PUBLISH))"
docker info >/dev/null 2>&1 || fail 'Docker daemon is unavailable. Start Docker and check docker context show / docker info, then rerun.'
for file in Dockerfile .dockerignore .nvmrc package.json package-lock.json frontend/package.json backend/package.json; do
  [[ -f "$file" && -r "$file" ]] || fail "Missing readable $file. Restore it from the repository."
done
NODE_VERSION="$(<.nvmrc)"
[[ "$NODE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail '.nvmrc must contain an exact Node.js version (major.minor.patch).'
if [[ ! -e .env && ! -L .env ]]; then
  [[ -f .env.example && -r .env.example ]] || fail 'Restore .env.example or create .env with the documented configuration.'
  (umask 077; set -o noclobber; cat .env.example > .env) || fail 'Could not create .env. Check repository permissions; existing files are never replaced.'
  echo "Created .env from safe defaults."
fi
[[ -f .env && -r .env ]] || fail '.env must be a readable regular file (or a symlink to one). Repair it yourself; it was not replaced.'
# Docker can echo malformed env-file lines in errors. Validate keys without
# printing values, evaluating shell syntax or inheriting bare keys from the host.
LINE_NUMBER=0
while IFS= read -r line || [[ -n "$line" ]]; do
  LINE_NUMBER=$((LINE_NUMBER + 1))
  line="${line%$'\r'}"
  [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
  [[ "$line" =~ ^[[:space:]]*[a-zA-Z_][a-zA-Z0-9_]*= ]] || fail "Invalid .env syntax at line $LINE_NUMBER. Use simple KEY=value entries or # comments; do not use bare keys or shell syntax."
done < .env
docker build --build-arg "NODE_VERSION=$NODE_VERSION" --tag hackalem:local "$ROOT" || fail 'Docker build failed. Check the build error above and registry access; no container was started.'
echo "Starting at http://localhost:$PORT_TO_PUBLISH — press Ctrl+C to stop."
# Only runtime configuration enters the container. Bind the host port to loopback.
exec docker run --rm --init --sig-proxy=true \
  --env-file "$ROOT/.env" --env HOST=0.0.0.0 --env PORT=3000 \
  --publish "127.0.0.1:$PORT_TO_PUBLISH:3000" hackalem:local
