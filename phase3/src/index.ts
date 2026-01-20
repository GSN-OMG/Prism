import { createServer } from 'node:http';
import { env } from './env.js';
import { createApp } from './app.js';
import { createPoolFromEnv } from './db/pool.js';
import { seedDemoData } from './demo/seedDemoData.js';

const { pool, mode } = await createPoolFromEnv(env.databaseUrl);

if (mode === 'memory' || env.seedDemoData) {
  await seedDemoData(pool);
}

const app = createApp({ pool });
const server = createServer(app);

server.listen(env.port, () => {
  console.log(`[prism] server listening on http://localhost:${env.port} (db=${mode})`);
  console.log(`[prism] gui: http://localhost:${env.port}/gui`);
});

const shutdown = async () => {
  server.close();
  await pool.end();
};

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
