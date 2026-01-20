import type { Pool } from 'pg';
import { Pool as PostgresPool } from 'pg';
import { newDb } from 'pg-mem';
import { schemaStatements } from './schema.js';

export type DbMode = 'postgres' | 'memory';

export async function initSchema(pool: Pick<Pool, 'query'>): Promise<void> {
  for (const statement of schemaStatements) {
    await pool.query(statement);
  }
}

export async function createPostgresPool(databaseUrl: string): Promise<Pool> {
  const pool = new PostgresPool({ connectionString: databaseUrl });
  await initSchema(pool);
  return pool;
}

export async function createMemoryPool(): Promise<Pool> {
  const mem = newDb({ autoCreateForeignKeyIndices: true });
  const { Pool: MemPool } = mem.adapters.createPg();
  const pool = new MemPool() as unknown as Pool;
  await initSchema(pool);
  return pool;
}

export async function createPoolFromEnv(
  databaseUrl?: string,
): Promise<{ pool: Pool; mode: DbMode }> {
  if (databaseUrl) {
    return { pool: await createPostgresPool(databaseUrl), mode: 'postgres' };
  }
  return { pool: await createMemoryPool(), mode: 'memory' };
}
