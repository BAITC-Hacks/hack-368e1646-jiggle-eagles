import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { AiError, generateText } from '../backend/src/openai.js';

// Root command: npm run openai:check -- --allow-paid-request.
// Export a user-authorized OPENAI_API_KEY and OPENAI_MODEL=gpt-4.1-nano yourself.
// No .env/key discovery. Never add this script to startup, health checks or ordinary tests.
// Explicit paid invocation: npm run openai:check -- --allow-paid-request
// Model/cost reference: https://developers.openai.com/api/docs/models/gpt-4.1-nano
const help = 'Optional paid connectivity check: export your authorized OPENAI_API_KEY and '
  + 'OPENAI_MODEL=gpt-4.1-nano, then run node --import tsx scripts/openai-check.ts --allow-paid-request. '
  + 'Sends only "Reply with exactly OK." with a 16-token output cap and no retries. '
  + 'Prints safe metadata only. No request is made without the flag.';

export async function runOpenAICheck(
  args: readonly string[],
  env: NodeJS.ProcessEnv,
  generate: typeof generateText = generateText,
): Promise<{ exitCode: number; output: string }> {
  if (args.length === 1 && args[0] === '--help') return { exitCode: 0, output: help };
  if (args.length !== 1 || args[0] !== '--allow-paid-request') return { exitCode: 2, output: help };
  if (!env.OPENAI_API_KEY?.trim() || !env.OPENAI_MODEL?.trim()) {
    return { exitCode: 2, output: 'Live verification pending: explicitly supply OPENAI_API_KEY and OPENAI_MODEL.' };
  }
  if (!['gpt-4.1-nano', 'gpt-4.1-nano-2025-04-14'].includes(env.OPENAI_MODEL.trim())) {
    return { exitCode: 2, output: 'For this low-cost check, explicitly set OPENAI_MODEL=gpt-4.1-nano.' };
  }
  try {
    const { diagnostics } = await generate('Reply with exactly OK.', { env, maxOutputTokens: 16, maxRetries: 0 });
    return { exitCode: 0, output: JSON.stringify({ event: 'openai_check', status: 'ok', ...diagnostics }) };
  } catch (error) {
    return { exitCode: 1, output: JSON.stringify({
      event: 'openai_check', status: 'error',
      ...(error instanceof AiError
        ? { code: error.code, message: error.message, ...error.diagnostics }
        : { code: 'UNEXPECTED', message: 'AI check failed; raw error details were suppressed.' }),
    }) };
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const result = await runOpenAICheck(process.argv.slice(2), process.env);
  (result.exitCode === 0 ? console.log : console.error)(result.output);
  process.exitCode = result.exitCode;
}
