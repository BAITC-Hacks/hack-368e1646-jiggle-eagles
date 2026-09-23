import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseEnv } from 'node:util';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig(() => {
  // Match Node's --env-file-if-exists: only root .env, no dotenv expansion or
  // mode-specific overrides. Never return environment values to the bundle.
  let env: ReturnType<typeof parseEnv> = {};
  try {
    env = parseEnv(readFileSync(fileURLToPath(new URL('../.env', import.meta.url)), 'utf8'));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
      throw new Error('Could not read root .env. Check that it is a readable file.');
    }
  }
  const port = process.env.PORT ?? env.PORT ?? '3000';
  if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
    throw new Error('Invalid configuration: PORT must be an integer from 1 to 65535.');
  }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: { '/api': { target: `http://127.0.0.1:${port}` } },
    },
  };
});
