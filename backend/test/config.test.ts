import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadConfig } from '../src/config.js';

test('configuration runs with no credentials and ignores unrelated environment variables', () => {
  assert.deepEqual(loadConfig({ UNRELATED: 'ignored' }), { HOST: '127.0.0.1', PORT: 3000, BODY_LIMIT_BYTES: 16384 });
  assert.deepEqual(loadConfig({ HOST: '0.0.0.0', PORT: '4100', BODY_LIMIT_BYTES: '1024' }), {
    HOST: '0.0.0.0', PORT: 4100, BODY_LIMIT_BYTES: 1024,
  });
});

test('invalid configuration reports field names and constraints without echoing values', () => {
  assert.throws(() => loadConfig({ HOST: 'secret-host', PORT: 'secret-port', BODY_LIMIT_BYTES: 'secret-limit' }), (error: unknown) => {
    assert.ok(error instanceof Error);
    assert.match(error.message, /HOST must be/);
    assert.match(error.message, /PORT must be/);
    assert.match(error.message, /BODY_LIMIT_BYTES must be/);
    assert.doesNotMatch(error.message, /secret/);
    return true;
  });
});

test('numeric configuration rejects empty, fractional, signed, exponential and out-of-range input', () => {
  for (const PORT of ['', '0', '-1', '65536', '1.2', '3e3', '+3000', ' 3000']) {
    assert.throws(() => loadConfig({ PORT }), /Invalid configuration/);
  }
  for (const BODY_LIMIT_BYTES of ['0', '-1', '1048577', '16kb', '1.5']) {
    assert.throws(() => loadConfig({ BODY_LIMIT_BYTES }), /Invalid configuration/);
  }
});
