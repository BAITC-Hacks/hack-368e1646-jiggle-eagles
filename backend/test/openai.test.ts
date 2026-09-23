import assert from 'node:assert/strict';
import { inspect } from 'node:util';
import { after, before, mock, test } from 'node:test';
import { AI_LIMITS, AiError, generateText } from '../src/openai.js';
import type { AiErrorCode, GenerateTextOptions } from '../src/openai.js';
import { runOpenAICheck } from '../../scripts/openai-check.js';

// All credentials and content here are synthetic; no test can use real fetch.
const env = { OPENAI_API_KEY: 'sk-synthetic-unit-test-only', OPENAI_MODEL: 'gpt-4.1-nano' };
const marker = 'private-synthetic-content';
before(() => { mock.method(globalThis, 'fetch', () => { throw new Error('External requests are forbidden in AI tests'); }); });
after(() => mock.restoreAll());

function completed(overrides: Record<string, unknown> = {}) {
  return {
    id: 'resp_synthetic', object: 'response', created_at: 0, status: 'completed',
    model: 'gpt-4.1-nano-2025-04-14', error: null, incomplete_details: null,
    output: [{ type: 'message', id: 'msg_synthetic', role: 'assistant', status: 'completed',
      content: [{ type: 'output_text', text: marker, annotations: [] }] }],
    usage: { input_tokens: 7, output_tokens: 2, total_tokens: 9 }, ...overrides,
  };
}

function transport(body: unknown, status = 200) {
  const calls: { url: string; init: RequestInit | undefined }[] = [];
  const fetch: typeof globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    return new Response(JSON.stringify(body), {
      status, headers: { 'content-type': 'application/json', 'retry-after-ms': '1' },
    });
  };
  return { fetch, calls };
}

function isFailure(code: AiErrorCode) {
  return (error: unknown) => {
    assert.ok(error instanceof AiError);
    assert.equal(error.code, code);
    assert.ok(Number.isFinite(error.diagnostics.durationMs) && error.diagnostics.durationMs >= 0);
    assert.doesNotMatch(inspect(error), /private-synthetic-content|sk-synthetic-unit-test-only/);
    assert.equal(error.cause, undefined);
    return true;
  };
}

test('Responses success sends capped, nonstored text and returns only allowlisted diagnostics', async () => {
  const fake = transport(completed());
  const result = await generateText(`  ${marker}  `, { env, fetch: fake.fetch });
  assert.equal(result.text, marker);
  assert.equal(fake.calls.length, 1);
  assert.equal(fake.calls[0].url, 'https://api.openai.com/v1/responses');
  assert.equal(fake.calls[0].init?.method, 'POST');
  assert.deepEqual(JSON.parse(String(fake.calls[0].init?.body)), {
    model: env.OPENAI_MODEL, input: marker, max_output_tokens: 256, store: false, stream: false,
  });
  assert.equal(new Headers(fake.calls[0].init?.headers).get('authorization'), `Bearer ${env.OPENAI_API_KEY}`);
  assert.deepEqual(Object.keys(result.diagnostics).sort(), ['durationMs', 'model', 'usage']);
  assert.equal(result.diagnostics.model, env.OPENAI_MODEL);
  assert.deepEqual(result.diagnostics.usage, { inputTokens: 7, outputTokens: 2, totalTokens: 9 });
  assert.ok(result.diagnostics.durationMs >= 0);
  assert.doesNotMatch(JSON.stringify(result.diagnostics), /private|sk-/);
});

test('configuration and input failures never invoke transport or echo values', async () => {
  const fake = transport(completed());
  for (const missing of [{}, { OPENAI_API_KEY: env.OPENAI_API_KEY }, { OPENAI_MODEL: env.OPENAI_MODEL },
    { ...env, OPENAI_API_KEY: '  ' }, { ...env, OPENAI_MODEL: '\n' }]) {
    await assert.rejects(generateText(marker, { env: missing, fetch: fake.fetch }), isFailure('MISSING_CONFIG'));
  }
  for (const invalid of [{ ...env, OPENAI_API_KEY: 'private key' }, { ...env, OPENAI_MODEL: 'private model\nvalue' },
    { ...env, OPENAI_MODEL: env.OPENAI_API_KEY }]) {
    await assert.rejects(generateText(marker, { env: invalid, fetch: fake.fetch }), isFailure('INVALID_CONFIG'));
  }
  for (const input of ['', ' \n ', 'x'.repeat(4001), null, 42]) {
    await assert.rejects(generateText(input as string, { env, fetch: fake.fetch }), isFailure('INVALID_INPUT'));
  }
  assert.equal(fake.calls.length, 0);
});

test('request limits cannot be raised or disabled with invalid options', async () => {
  const fake = transport(completed());
  for (const maxOutputTokens of [0, 15, 257, 1.5, NaN, Infinity]) {
    await assert.rejects(generateText(marker, { env, fetch: fake.fetch, maxOutputTokens }), isFailure('INVALID_OPTIONS'));
  }
  for (const maxRetries of [-1, 2, 0.5, NaN, Infinity]) {
    await assert.rejects(generateText(marker, {
      env, fetch: fake.fetch, maxRetries: maxRetries as GenerateTextOptions['maxRetries'],
    }), isFailure('INVALID_OPTIONS'));
  }
  assert.equal(fake.calls.length, 0);
});

for (const [status, code, type, param, expected] of [
  [401, 'invalid_api_key', 'invalid_request_error', null, 'AUTHENTICATION'],
  [403, null, 'permission_error', null, 'PERMISSION_DENIED'],
  [404, 'model_not_found', 'invalid_request_error', null, 'MODEL_UNAVAILABLE'],
  [400, 'model_not_available', 'invalid_request_error', 'model', 'MODEL_UNAVAILABLE'],
  [403, null, 'permission_error', 'model', 'MODEL_UNAVAILABLE'],
  [429, 'insufficient_quota', 'insufficient_quota', null, 'QUOTA_EXHAUSTED'],
  [429, null, 'insufficient_quota', null, 'QUOTA_EXHAUSTED'],
  [429, 'organization_spend_limit_exceeded', 'billing_error', null, 'QUOTA_EXHAUSTED'],
  [429, 'project_spend_limit_exceeded', 'billing_error', null, 'QUOTA_EXHAUSTED'],
  [429, 'organization_usage_limit_exceeded', 'billing_error', null, 'QUOTA_EXHAUSTED'],
  [429, 'rate_limit_exceeded', 'rate_limit_error', null, 'RATE_LIMITED'],
  [429, 'slow_down', 'rate_limit_error', null, 'RATE_LIMITED'],
  [408, null, null, null, 'TIMEOUT'],
  [400, null, 'invalid_request_error', 'input', 'REQUEST_REJECTED'],
  [503, 'server_error', null, null, 'UPSTREAM'],
] as const) {
  test(`safe error mapping: ${status}/${code ?? type} → ${expected}`, async () => {
    const fake = transport({ error: { code, type, param, message: `${marker} ${env.OPENAI_API_KEY}` } }, status);
    await assert.rejects(generateText(marker, { env, fetch: fake.fetch }), isFailure(expected));
    assert.equal(fake.calls.length, status === 408 || status === 429 || status >= 500 ? 2 : 1);
  });
}

test('SDK alone retries a transient failure and can then succeed', async () => {
  let attempts = 0;
  const fetch: typeof globalThis.fetch = async () => ++attempts === 1
    ? new Response(JSON.stringify({ error: { code: 'server_error', message: marker } }), {
      status: 503, headers: { 'content-type': 'application/json', 'retry-after-ms': '1' },
    })
    : new Response(JSON.stringify(completed()), { headers: { 'content-type': 'application/json' } });
  assert.equal((await generateText(marker, { env, fetch })).text, marker);
  assert.equal(attempts, 2);
});

test('connection failures suppress raw causes and permit disabling SDK retries', async () => {
  let attempts = 0;
  await assert.rejects(generateText(marker, { env, maxRetries: 0, fetch: async () => {
    attempts++;
    throw new Error(`${marker} ${env.OPENAI_API_KEY}`);
  } }), isFailure('CONNECTION'));
  assert.equal(attempts, 1);
});

test('SDK attempt timeout is explicit and becomes a safe timeout error', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let entered!: () => void;
  const fetching = new Promise<void>((resolve) => { entered = resolve; });
  const pending = assert.rejects(generateText(marker, { env, maxRetries: 0, fetch: async (_url, init) => {
    entered();
    return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException(marker, 'AbortError')), { once: true });
    });
  } }), isFailure('TIMEOUT'));
  await fetching;
  t.mock.timers.tick(AI_LIMITS.timeoutMs);
  await pending;
});

test('overall deadline cancels SDK retry backoff without another attempt', async (t) => {
  const controller = new AbortController();
  t.mock.method(AbortSignal, 'timeout', (milliseconds: number) => {
    assert.equal(milliseconds, 15_000);
    return controller.signal;
  });
  let attempts = 0;
  const pending = assert.rejects(generateText(marker, { env, fetch: async () => {
    attempts++;
    setImmediate(() => controller.abort(new DOMException(marker, 'TimeoutError')));
    return new Response(JSON.stringify({ error: { code: 'rate_limit_exceeded', message: marker } }), {
      status: 429, headers: { 'content-type': 'application/json', 'retry-after': '30' },
    });
  } }), isFailure('TIMEOUT'));
  await pending;
  assert.equal(attempts, 1);
});

test('partial, refused, failed and empty responses are not reported as successful text', async () => {
  for (const [overrides, expected] of [
    [{ status: 'incomplete', incomplete_details: { reason: 'max_output_tokens' } }, 'OUTPUT_LIMIT'],
    [{ status: 'incomplete', incomplete_details: { reason: 'content_filter' } }, 'REFUSED'],
    [{ status: 'in_progress' }, 'INCOMPLETE'],
    [{ status: 'failed', error: { code: 'server_error', message: marker } }, 'UPSTREAM'],
    [{ status: 'failed', error: { code: 'rate_limit_exceeded', message: marker } }, 'RATE_LIMITED'],
    [{ output: [] }, 'EMPTY_RESPONSE'],
    [{ output: [{ type: 'message', content: [{ type: 'refusal', refusal: marker }] }] }, 'REFUSED'],
  ] as const) {
    const fake = transport(completed(overrides));
    await assert.rejects(generateText(marker, { env, fetch: fake.fetch }), (error: unknown) => {
      isFailure(expected)(error);
      assert.deepEqual((error as AiError).diagnostics.usage, { inputTokens: 7, outputTokens: 2, totalTokens: 9 });
      return true;
    });
    assert.equal(fake.calls.length, 1);
  }
});

test('absent or malformed usage is omitted; extra response fields never enter diagnostics', async () => {
  for (const usage of [undefined, null, { input_tokens: marker, output_tokens: 2, total_tokens: 9 }]) {
    const fake = transport(completed({ usage, model: marker, metadata: { secret: marker } }));
    const result = await generateText(marker, { env, fetch: fake.fetch });
    assert.deepEqual(Object.keys(result.diagnostics).sort(), ['durationMs', 'model']);
    assert.doesNotMatch(JSON.stringify(result.diagnostics), /private/);
  }
});

test('SDK logs and inherited endpoint/project/credential settings are overridden', async (t) => {
  const original = { ...process.env };
  t.after(() => { process.env = original; });
  Object.assign(process.env, {
    OPENAI_LOG: 'debug', OPENAI_BASE_URL: 'https://synthetic.invalid/v1',
    OPENAI_ORG_ID: marker, OPENAI_PROJECT_ID: marker, OPENAI_ADMIN_KEY: marker,
  });
  const logs: unknown[][] = [];
  for (const method of ['log', 'debug', 'info', 'warn', 'error'] as const) {
    t.mock.method(console, method, (...args: unknown[]) => { logs.push(args); });
  }
  const fake = transport(completed());
  await generateText(marker, { env, fetch: fake.fetch });
  assert.equal(fake.calls[0].url, 'https://api.openai.com/v1/responses');
  const headers = new Headers(fake.calls[0].init?.headers);
  assert.equal(headers.get('openai-organization'), null);
  assert.equal(headers.get('openai-project'), null);
  assert.equal(headers.get('authorization'), `Bearer ${env.OPENAI_API_KEY}`);
  const failure = transport({ error: { message: marker } }, 401);
  await assert.rejects(generateText(marker, { env, fetch: failure.fetch }), isFailure('AUTHENTICATION'));
  assert.deepEqual(logs, []);
});

test('check script requires explicit consent, supplied configuration and a low-cost model', async () => {
  let attempts = 0;
  const generate: typeof generateText = async () => { attempts++; throw new Error('must not call'); };
  for (const args of [[], ['--unknown'], ['--allow-paid-request', '--unknown']]) {
    assert.equal((await runOpenAICheck(args, env, generate)).exitCode, 2);
  }
  assert.equal((await runOpenAICheck(['--help'], env, generate)).exitCode, 0);
  const missing = await runOpenAICheck(['--allow-paid-request'], {}, generate);
  assert.equal(missing.exitCode, 2);
  assert.match(missing.output, /Live verification pending/);
  assert.equal((await runOpenAICheck(['--allow-paid-request'], { ...env, OPENAI_MODEL: 'other-model' }, generate)).exitCode, 2);
  assert.equal(attempts, 0);
});

test('check script uses synthetic input, 16 output tokens, zero retries and prints no text', async () => {
  const fake = transport(completed());
  const generate: typeof generateText = async (input, options) => {
    assert.equal(input, 'Reply with exactly OK.');
    assert.equal(options?.maxOutputTokens, 16);
    assert.equal(options?.maxRetries, 0);
    return generateText(input, { ...options, fetch: fake.fetch });
  };
  const result = await runOpenAICheck(['--allow-paid-request'], env, generate);
  assert.equal(result.exitCode, 0);
  assert.equal(fake.calls.length, 1);
  assert.equal(JSON.parse(String(fake.calls[0].init?.body)).max_output_tokens, 16);
  assert.deepEqual(Object.keys(JSON.parse(result.output)).sort(), ['durationMs', 'event', 'model', 'status', 'usage']);
  assert.doesNotMatch(result.output, /private|sk-/);
});

test('check script reports safe failures and never retries a failed connectivity attempt', async () => {
  const fake = transport({ error: { code: 'rate_limit_exceeded', message: marker } }, 429);
  const result = await runOpenAICheck(['--allow-paid-request'], env,
    (input, options) => generateText(input, { ...options, fetch: fake.fetch }));
  assert.equal(result.exitCode, 1);
  assert.equal(JSON.parse(result.output).code, 'RATE_LIMITED');
  assert.equal(fake.calls.length, 1);
  assert.doesNotMatch(result.output, /private|sk-/);
  const unexpected = await runOpenAICheck(['--allow-paid-request'], env, async () => { throw new Error(marker); });
  assert.equal(unexpected.exitCode, 1);
  assert.doesNotMatch(unexpected.output, /private/);
});
