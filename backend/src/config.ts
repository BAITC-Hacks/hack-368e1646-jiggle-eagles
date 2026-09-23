import { z } from 'zod';

const integer = (fallback: string, max: number) => z.string().regex(/^\d+$/)
  .default(fallback).transform(Number).pipe(z.number().int().min(1).max(max));

const configSchema = z.object({
  HOST: z.enum(['127.0.0.1', '0.0.0.0']).default('127.0.0.1'),
  PORT: integer('3000', 65535),
  BODY_LIMIT_BYTES: integer('16384', 1048576),
});

export type Config = z.infer<typeof configSchema>;

const descriptions: Record<string, string> = {
  HOST: 'must be 127.0.0.1 or 0.0.0.0',
  PORT: 'must be an integer from 1 to 65535',
  BODY_LIMIT_BYTES: 'must be an integer from 1 to 1048576',
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const result = configSchema.safeParse(env);
  if (!result.success) {
    const fields = [...new Set(result.error.issues.map((issue) => String(issue.path[0])))];
    throw new Error(`Invalid configuration:\n${fields.map((field) => `- ${field} ${descriptions[field]}`).join('\n')}`);
  }
  return result.data;
}
