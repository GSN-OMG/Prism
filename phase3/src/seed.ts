import { env } from './env.js';
import { createPostgresPool } from './db/pool.js';
import { seedDemoData } from './demo/seedDemoData.js';

if (!env.databaseUrl) {
  console.error('[prism] DATABASE_URL is required for seeding a persistent database.');
  process.exit(1);
}

const pool = await createPostgresPool(env.databaseUrl);
await seedDemoData(pool);
await pool.end();
console.log('[prism] seed complete');
