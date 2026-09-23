import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createApp, log } from './app.js';
import { loadConfig } from './config.js';

let config;
try {
  config = loadConfig();
} catch (error) {
  console.error(error instanceof Error ? error.message : 'Invalid configuration.');
  process.exit(1);
}

const development = process.argv.includes('--dev');
const frontendDir = fileURLToPath(new URL('../../frontend/dist/', import.meta.url));
if (!development && !existsSync(`${frontendDir}/index.html`)) {
  console.error('Frontend build is missing. Run npm run build from the repository root.');
  process.exit(1);
}

const server = createApp(config, { frontendDir: development ? undefined : frontendDir })
  .listen(config.PORT, config.HOST);

server.once('listening', () => {
  console.log(`Connectivity test: http://${config.HOST === '0.0.0.0' ? 'localhost' : config.HOST}:${config.PORT}`);
});

server.on('error', (error: NodeJS.ErrnoException) => {
  console.error(error.code === 'EADDRINUSE'
    ? 'Startup failed: port is already in use. Change PORT or stop its owner yourself.'
    : 'Startup failed: could not listen on the configured address.');
  process.exitCode = 1;
});

let stopping = false;
function shutdown() {
  if (stopping) return;
  stopping = true;
  log({ event: 'shutdown' });
  server.close(() => { process.exitCode = 0; });
  setTimeout(() => { server.closeAllConnections(); }, 5000).unref();
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
