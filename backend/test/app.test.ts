import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { echoText } from '../../frontend/src/api.js';
import { createApp } from '../src/app.js';
import type { LogEntry } from '../src/app.js';
import { loadConfig } from '../src/config.js';

let server: Server;
let base: string;
let staticDir: string;
const logs: LogEntry[] = [];

before(async () => {
  staticDir = await mkdtemp(path.join(os.tmpdir(), 'hackalem-test-'));
  await writeFile(path.join(staticDir, 'index.html'), '<h1>Connectivity test</h1>');
  await writeFile(path.join(staticDir, 'app.js'), 'console.log("fixture");');
  server = createApp(loadConfig({}), { frontendDir: staticDir, logger: (entry) => logs.push(entry) })
    .listen(0, '127.0.0.1');
  await once(server, 'listening');
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

after(async () => {
  if (server?.listening) {
    server.closeAllConnections();
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
  if (staticDir) await rm(staticDir, { recursive: true, force: true });
});

function post(body: unknown) {
  return fetch(`${base}/api/echo`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
}

async function expectError(response: Response, status: number, code: string) {
  assert.equal(response.status, status);
  assert.match(response.headers.get('content-type') ?? '', /application\/json/);
  const body = await response.json() as {
    error: { code: string; message: string; issues?: unknown[]; stack?: unknown };
  };
  assert.deepEqual(Object.keys(body), ['error']);
  assert.equal(body.error.code, code);
  assert.equal(typeof body.error.message, 'string');
  assert.equal(body.error.stack, undefined);
  return body;
}

test('health returns JSON and a generated request ID', async () => {
  const response = await fetch(`${base}/api/health`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ok' });
  assert.match(response.headers.get('x-request-id') ?? '', /^[a-f0-9-]{36}$/);
  assert.equal(response.headers.get('x-powered-by'), null);
});

test('echo trims valid input and accepts Unicode and the 1000-character boundary', async () => {
  for (const text of ['  Hello, HackAlem!  ', 'Сәлем, әлем!', 'x'.repeat(1000)]) {
    const response = await post({ text });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { text: text.trim() });
  }
});

test('the frontend API client completes a real HTTP round trip and surfaces validation errors', async () => {
  assert.equal(await echoText('  frontend → backend  ', base), 'frontend → backend');
  await assert.rejects(echoText('   ', base), /Send an object containing only text/);
});

for (const [name, input] of [
  ['missing text', {}], ['empty text', { text: '' }], ['whitespace', { text: ' \n\t ' }],
  ['wrong type', { text: 42 }], ['null text', { text: null }], ['overlong text', { text: 'x'.repeat(1001) }],
  ['unknown key', { text: 'hello', extra: true }], ['array body', ['hello']],
] as const) {
  test(`echo rejects ${name}`, async () => {
    const body = await expectError(await post(input), 400, 'VALIDATION_ERROR');
    assert.ok(body.error.issues && body.error.issues.length > 0);
  });
}

test('malformed and primitive JSON use the same error envelope', async () => {
  for (const body of ['{"text":', 'null', '42']) {
    await expectError(await fetch(`${base}/api/echo`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
    }), 400, 'INVALID_JSON');
  }
});

test('body limit rejects oversized input before validation', async () => {
  await expectError(await post({ text: 'x'.repeat(20000) }), 413, 'PAYLOAD_TOO_LARGE');
});

test('unsupported content types and encodings return JSON errors', async () => {
  await expectError(await fetch(`${base}/api/echo`, { method: 'POST', body: 'hello' }), 415, 'UNSUPPORTED_MEDIA_TYPE');
  await expectError(await fetch(`${base}/api/echo`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Encoding': 'gzip' }, body: '{}',
  }), 415, 'UNSUPPORTED_MEDIA_TYPE');
});

test('missing API endpoints and wrong methods never fall through to HTML', async () => {
  await expectError(await fetch(`${base}/api/missing`), 404, 'NOT_FOUND');
  await expectError(await fetch(`${base}/api/health`, { method: 'POST' }), 404, 'NOT_FOUND');
  await expectError(await fetch(`${base}/missing`), 404, 'NOT_FOUND');
});

test('production serves the frontend and assets from the same server', async () => {
  const index = await fetch(`${base}/`);
  assert.equal(index.status, 200);
  assert.match(index.headers.get('content-type') ?? '', /text\/html/);
  assert.match(await index.text(), /Connectivity test/);
  const asset = await fetch(`${base}/app.js`);
  assert.equal(asset.status, 200);
  assert.match(await asset.text(), /fixture/);
});

test('logs exclude submitted data, URLs, headers and unknown field names', async () => {
  const marker = 'private-test-marker';
  const start = logs.length;
  const response = await fetch(`${base}/api/echo?token=${marker}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${marker}`, 'X-Request-Id': marker },
    body: JSON.stringify({ text: marker, [marker]: marker }),
  });
  await expectError(response, 400, 'VALIDATION_ERROR');
  await fetch(`${base}/${marker}`);
  const recent = logs.slice(start);
  assert.ok(recent.length >= 2);
  assert.ok(!JSON.stringify(recent).includes(marker));
  for (const entry of recent) {
    assert.deepEqual(Object.keys(entry).sort(), ['durationMs', 'event', 'requestId', 'route', 'status']);
  }
});
