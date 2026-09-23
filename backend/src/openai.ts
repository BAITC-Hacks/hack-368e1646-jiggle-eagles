import OpenAI from 'openai';
import type { ResponseUsage } from 'openai/resources/responses/responses';

// Server-only, opt-in helper. Importing this module does not read configuration or call AI.
// SDK: https://developers.openai.com/api/reference/typescript
// API: https://developers.openai.com/api/reference/typescript/resources/responses/methods/create
// Errors: https://developers.openai.com/api/docs/guides/error-codes
export const AI_LIMITS = Object.freeze({
  timeoutMs: 10_000, // Per SDK attempt.
  deadlineMs: 15_000, // Includes SDK retries, backoff and reading the response body.
  maxOutputTokens: 256, // Includes reasoning tokens; callers can only lower this cap.
  maxRetries: 1, // At most two attempts, owned entirely by the SDK.
  maxInputCharacters: 4_000,
});

const messages = {
  MISSING_CONFIG: 'Set both OPENAI_API_KEY and OPENAI_MODEL in the server environment before requesting AI.',
  INVALID_CONFIG: 'OPENAI_MODEL must be a model identifier; OPENAI_API_KEY must contain no whitespace.',
  INVALID_INPUT: 'AI input must contain 1–4000 characters after trimming.',
  INVALID_OPTIONS: 'Use an integer maxOutputTokens from 16 to 256 and maxRetries of 0 or 1.',
  AUTHENTICATION: 'OpenAI rejected OPENAI_API_KEY. Check or replace the authorized project key.',
  PERMISSION_DENIED: 'The OpenAI project lacks permission for this request. Check key and project permissions.',
  MODEL_UNAVAILABLE: 'OPENAI_MODEL is unavailable or inaccessible. Check its identifier, project access and Responses API support.',
  QUOTA_EXHAUSTED: 'OpenAI quota or a spend limit is exhausted. Check project billing and limits before another request.',
  RATE_LIMITED: 'OpenAI rate limited the request. Reduce request frequency and wait before trying again.',
  TIMEOUT: 'The OpenAI request timed out. Check connectivity or try a shorter request later.',
  CONNECTION: 'Could not connect to OpenAI. Check server network connectivity.',
  REQUEST_REJECTED: 'OpenAI rejected the request. Check model support and request parameters.',
  UPSTREAM: 'OpenAI could not complete the request. Try again later.',
  OUTPUT_LIMIT: 'OpenAI reached the output token cap. Request a shorter answer; partial text was discarded.',
  REFUSED: 'OpenAI declined to produce text for this request.',
  INCOMPLETE: 'OpenAI did not return a completed response; partial text was discarded.',
  EMPTY_RESPONSE: 'OpenAI completed the request without usable text.',
} as const;

export type AiErrorCode = keyof typeof messages;
export type AiDiagnostics = {
  durationMs: number;
  model?: string; // Requested model, never an unfiltered server-supplied value.
  usage?: { inputTokens: number; outputTokens: number; totalTokens: number };
};

export class AiError extends Error {
  readonly code: AiErrorCode;
  readonly diagnostics: AiDiagnostics;

  constructor(code: AiErrorCode, diagnostics: AiDiagnostics) {
    super(messages[code]);
    this.name = 'AiError';
    this.code = code;
    this.diagnostics = diagnostics;
    // Deliberately omit raw SDK errors/causes: they can contain request or response data.
  }
}

export type GenerateTextOptions = {
  env?: NodeJS.ProcessEnv;
  maxOutputTokens?: number;
  maxRetries?: 0 | 1;
  fetch?: typeof globalThis.fetch; // SDK transport seam for offline tests.
};

function failureCode(status?: number, code?: string | null, type?: string, param?: string | null): AiErrorCode {
  if (status === 401) return 'AUTHENTICATION';
  if (['insufficient_quota', 'billing_hard_limit_reached', 'organization_spend_limit_exceeded',
    'project_spend_limit_exceeded', 'organization_usage_limit_exceeded'].includes(code ?? '')
    || type === 'insufficient_quota') return 'QUOTA_EXHAUSTED';
  if (status === 404 || code === 'model_not_found' || code === 'model_not_available'
    || ((status === 400 || status === 403) && param === 'model')) return 'MODEL_UNAVAILABLE';
  if (status === 403) return 'PERMISSION_DENIED';
  if (status === 429 || code === 'rate_limit_exceeded' || code === 'slow_down') return 'RATE_LIMITED';
  if (status === 408) return 'TIMEOUT';
  if (status && status >= 400 && status < 500) return 'REQUEST_REJECTED';
  return 'UPSTREAM';
}

function safeUsage(usage: ResponseUsage | undefined): AiDiagnostics['usage'] {
  if (!usage) return undefined;
  const { input_tokens, output_tokens, total_tokens } = usage;
  if (![input_tokens, output_tokens, total_tokens].every((value) => Number.isSafeInteger(value) && value >= 0)) {
    return undefined;
  }
  return { inputTokens: input_tokens, outputTokens: output_tokens, totalTokens: total_tokens };
}

/** One nonstreaming Responses request. Log only diagnostics, never the returned text. */
export async function generateText(input: string, options: GenerateTextOptions = {}): Promise<{
  text: string;
  diagnostics: AiDiagnostics;
}> {
  const started = performance.now();
  let model: string | undefined;
  let usage: AiDiagnostics['usage'];
  const diagnostics = (): AiDiagnostics => ({
    durationMs: Math.max(0, Math.round(performance.now() - started)),
    ...(model ? { model } : {}),
    ...(usage ? { usage } : {}),
  });
  const fail = (code: AiErrorCode) => new AiError(code, diagnostics());
  const env = options.env ?? process.env;
  const apiKey = env.OPENAI_API_KEY?.trim();
  const requestedModel = env.OPENAI_MODEL?.trim();
  if (!apiKey || !requestedModel) throw fail('MISSING_CONFIG');
  if (/\s/.test(apiKey) || !/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,199}$/.test(requestedModel)
    || requestedModel.startsWith('sk-') || requestedModel === apiKey) throw fail('INVALID_CONFIG');
  model = requestedModel;
  if (typeof input !== 'string' || !input.trim() || input.trim().length > AI_LIMITS.maxInputCharacters) {
    throw fail('INVALID_INPUT');
  }
  const maxOutputTokens = options.maxOutputTokens ?? AI_LIMITS.maxOutputTokens;
  const maxRetries = options.maxRetries ?? AI_LIMITS.maxRetries;
  if (!Number.isInteger(maxOutputTokens) || maxOutputTokens < 16 || maxOutputTokens > AI_LIMITS.maxOutputTokens
    || !Number.isInteger(maxRetries) || maxRetries < 0 || maxRetries > AI_LIMITS.maxRetries) {
    throw fail('INVALID_OPTIONS');
  }
  const deadline = AbortSignal.timeout(AI_LIMITS.deadlineMs);
  try {
    const client = new OpenAI({
      apiKey,
      adminAPIKey: null,
      webhookSecret: null,
      baseURL: 'https://api.openai.com/v1',
      organization: null,
      project: null,
      timeout: AI_LIMITS.timeoutMs,
      maxRetries,
      logLevel: 'off', // Overrides OPENAI_LOG; diagnostics are returned, never logged here.
      ...(options.fetch ? { fetch: options.fetch } : {}),
    });
    const response = await client.responses.create({
      model,
      input: input.trim(),
      max_output_tokens: maxOutputTokens,
      store: false,
      stream: false,
    }, { signal: deadline });
    usage = safeUsage(response.usage);
    if (response.error) throw fail(failureCode(undefined, response.error.code));
    if (response.status === 'incomplete' && response.incomplete_details?.reason === 'max_output_tokens') {
      throw fail('OUTPUT_LIMIT');
    }
    if (response.incomplete_details?.reason === 'content_filter'
      || response.output.some((item) => item.type === 'message'
        && item.content.some((part) => part.type === 'refusal'))) throw fail('REFUSED');
    if (response.status !== 'completed') throw fail('INCOMPLETE');
    if (!response.output_text?.trim()) throw fail('EMPTY_RESPONSE');
    return { text: response.output_text, diagnostics: diagnostics() };
  } catch (error) {
    if (error instanceof AiError) throw error;
    if (deadline.aborted || error instanceof OpenAI.APIConnectionTimeoutError) throw fail('TIMEOUT');
    if (error instanceof OpenAI.APIConnectionError) throw fail('CONNECTION');
    if (error instanceof OpenAI.APIError) throw fail(failureCode(error.status, error.code, error.type, error.param));
    throw fail('UPSTREAM');
  }
}
