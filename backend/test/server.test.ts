import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { promisify } from 'node:util';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const run = promisify(execFile);

test('occupied-port startup fails without announcing readiness or disturbing its owner', async (t) => {
  const owner = createServer((_req, res) => res.end('synthetic port owner'));
  owner.listen(0, '127.0.0.1');
  await once(owner, 'listening');
  t.after(async () => {
    owner.closeAllConnections();
    await new Promise<void>((resolve, reject) => owner.close((error) => error ? reject(error) : resolve()));
  });
  const port = (owner.address() as AddressInfo).port;
  await assert.rejects(run(process.execPath, ['--import', 'tsx', 'backend/src/server.ts', '--dev'], {
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
    // Never inherit credentials or load a developer's .env in this subprocess.
    env: { HOST: '127.0.0.1', PORT: String(port) },
    timeout: 10_000,
  }), (error: unknown) => {
    const failure = error as Error & { code: number; stdout: string; stderr: string };
    assert.equal(failure.code, 1);
    assert.match(failure.stderr, /port is already in use/);
    assert.doesNotMatch(failure.stdout, /Connectivity test:|http:\/\//);
    return true;
  });
  const response = await fetch(`http://127.0.0.1:${port}`, { signal: AbortSignal.timeout(2000) });
  assert.equal(await response.text(), 'synthetic port owner');
});
