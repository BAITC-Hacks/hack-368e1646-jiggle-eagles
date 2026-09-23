#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail() { echo "Launch failed: $1" >&2; exit 1; }
[[ -f .nvmrc && -r .nvmrc ]] || fail 'Missing readable .nvmrc. Restore the repository version pin.'
EXPECTED="$(<.nvmrc)"
[[ "$EXPECTED" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail '.nvmrc must contain an exact Node.js version (major.minor.patch).'
for tool in node npm; do
  command -v "$tool" >/dev/null 2>&1 || fail "Missing $tool. Run nvm install and nvm use to activate the Node.js version in .nvmrc with its bundled npm, then rerun."
done
[[ "$(node --version)" == "v$EXPECTED" ]] || fail "Use Node.js $EXPECTED (see .nvmrc), then rerun."
npm --version >/dev/null || fail 'Could not run npm. Use the npm bundled with the Node.js version in .nvmrc, then rerun.'
for file in package.json package-lock.json frontend/package.json backend/package.json; do
  [[ -f "$file" && -r "$file" ]] || fail "Missing readable $file. Restore it from the repository; do not generate a new lockfile."
done
if [[ ! -e .env && ! -L .env ]]; then
  [[ -f .env.example && -r .env.example ]] || fail 'Restore .env.example or create .env with the documented configuration.'
  (umask 077; set -o noclobber; cat .env.example > .env) || fail 'Could not create .env. Check repository permissions; existing files are never replaced.'
  echo "Created .env from safe defaults."
fi
[[ -f .env && -r .env ]] || fail '.env must be a readable regular file (or a symlink to one). Repair it yourself; it was not replaced.'
# Keep build tools available even when the caller exports NODE_ENV=production.
npm ci --include=dev --no-audit --no-fund || fail 'Locked dependency installation failed. Check the npm error above, registry access and lockfile consistency; no build or start was attempted.'
npm run build || fail 'Production build failed. Fix the error above, then rerun; no server was started.'
echo "Starting the app; its URL will be printed below. Press Ctrl+C to stop."
NODE_ENV=production exec npm start
