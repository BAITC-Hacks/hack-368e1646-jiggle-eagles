import { randomUUID } from 'node:crypto';
import path from 'node:path';
import express from 'express';
import type { ErrorRequestHandler, Response } from 'express';
import { z } from 'zod';
import type { Config } from './config.js';

export type LogEntry = Record<string, string | number>;
export type Logger = (entry: LogEntry) => void;
export const log: Logger = (entry) => console.log(JSON.stringify(entry));

const echoSchema = z.strictObject({
  text: z.string({ error: 'text must be a string.' })
    .trim().min(1, 'text must contain at least one non-whitespace character.')
    .max(1000, 'text must contain at most 1000 characters.'),
});

function fail(res: Response, status: number, code: string, message: string) {
  return res.status(status).json({ error: { code, message } });
}

export function createApp(config: Config, options: { frontendDir?: string; logger?: Logger } = {}) {
  const app = express();
  const logger = options.logger ?? log;
  app.disable('x-powered-by');
  app.use((req, res, next) => {
    const started = performance.now();
    const requestId = randomUUID();
    res.setHeader('X-Request-Id', requestId);
    res.setHeader('X-Content-Type-Options', 'nosniff');
    // Route labels are assigned below. Never log URLs, headers, bodies or error messages.
    res.locals.route = 'other';
    res.on('finish', () => logger({
      event: 'request', requestId, route: String(res.locals.route),
      status: res.statusCode, durationMs: Math.round(performance.now() - started),
    }));
    next();
  });

  app.get('/api/health', (_req, res) => {
    res.locals.route = 'health';
    res.json({ status: 'ok' });
  });

  app.post('/api/echo', (req, res, next) => {
    res.locals.route = 'echo';
    if (!req.is('application/json')) {
      fail(res, 415, 'UNSUPPORTED_MEDIA_TYPE', 'Use Content-Type: application/json.');
      return;
    }
    next();
  }, express.json({ limit: config.BODY_LIMIT_BYTES, inflate: false }), (req, res) => {
    const parsed = echoSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: {
        code: 'VALIDATION_ERROR',
        message: 'Send an object containing only text: a string of 1–1000 characters after trimming.',
        issues: parsed.error.issues.map((issue) => ({
          field: issue.path[0] === 'text' ? 'text' : 'body',
          message: issue.path[0] === 'text' ? issue.message : 'Expected an object containing only the text field.',
        })),
      } });
      return;
    }
    res.json({ text: parsed.data.text });
  });

  app.use('/api', (_req, res) => {
    res.locals.route = 'api-not-found';
    fail(res, 404, 'NOT_FOUND', 'API endpoint not found.');
  });

  if (options.frontendDir) {
    app.use(express.static(path.resolve(options.frontendDir), { dotfiles: 'deny' }));
  }
  app.use((_req, res) => { fail(res, 404, 'NOT_FOUND', 'Resource not found.'); });

  const handleError: ErrorRequestHandler = (error: unknown, _req, res, next) => {
    if (res.headersSent) { next(error); return; }
    const type = (error as { type?: unknown } | null)?.type;
    if (type === 'entity.too.large') {
      fail(res, 413, 'PAYLOAD_TOO_LARGE', 'Request body exceeds the configured size limit.');
    } else if (type === 'entity.parse.failed') {
      fail(res, 400, 'INVALID_JSON', 'Request body must be valid JSON.');
    } else if (type === 'encoding.unsupported' || type === 'charset.unsupported') {
      fail(res, 415, 'UNSUPPORTED_MEDIA_TYPE', 'Use uncompressed UTF-8 JSON.');
    } else if (type === 'request.aborted' || type === 'request.size.invalid') {
      fail(res, 400, 'INVALID_REQUEST', 'Request body could not be read.');
    } else {
      logger({ event: 'internal_error', requestId: String(res.getHeader('X-Request-Id')) });
      fail(res, 500, 'INTERNAL_ERROR', 'An unexpected error occurred.');
    }
  };
  app.use(handleError);
  return app;
}
