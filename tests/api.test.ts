import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import request from 'supertest';
import type { Pool } from 'pg';
import { createApp } from '../src/app.js';
import { createMemoryPool } from '../src/db/pool.js';
import { seedDemoData } from '../src/demo/seedDemoData.js';

describe('phase3 GUI API', () => {
  let pool: Pool;

  beforeAll(async () => {
    pool = await createMemoryPool();
    await seedDemoData(pool);
  });

  afterAll(async () => {
    await pool.end();
  });

  it('lists cases', async () => {
    const app = createApp({ pool });
    const res = await request(app).get('/cases').expect(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);
    expect(res.body[0]).toHaveProperty('id');
  });

  it('shows case details, events, and reviews prompt updates', async () => {
    const app = createApp({ pool });

    const casesRes = await request(app).get('/cases').expect(200);
    const caseId = casesRes.body[0].id as string;

    const caseRes = await request(app).get(`/cases/${caseId}`).expect(200);
    expect(caseRes.body.id).toBe(caseId);

    const eventsRes = await request(app)
      .get(`/cases/${caseId}/events`)
      .query({ actor_type: 'human' })
      .expect(200);
    for (const ev of eventsRes.body as Array<{ actor_type: string }>) {
      expect(ev.actor_type).toBe('human');
    }

    const promptUpdatesRes = await request(app)
      .get('/prompt-updates')
      .query({ case_id: caseId, status: 'proposed' })
      .expect(200);
    expect(promptUpdatesRes.body.length).toBeGreaterThan(0);
    const promptUpdateId = promptUpdatesRes.body[0].id as string;

    const reviewRes = await request(app)
      .post(`/prompt-updates/${promptUpdateId}/review`)
      .send({ action: 'approve', comment: 'looks good', reviewer: 'test' })
      .set('Content-Type', 'application/json')
      .expect(200);
    expect(reviewRes.body.status).toBe('approved');

    const applyRes = await request(app)
      .post(`/prompt-updates/${promptUpdateId}/apply`)
      .send({})
      .set('Content-Type', 'application/json')
      .expect(200);
    expect(applyRes.body.promptUpdate.status).toBe('applied');
    expect(applyRes.body.rolePrompt.role).toBe('issue-analysis-agent');
    expect(applyRes.body.rolePrompt.version).toBe(2);
    expect(applyRes.body.rolePrompt.is_active).toBe(true);

    const rolePrompts = await pool.query<{ version: number; is_active: boolean }>(
      `SELECT version, is_active FROM role_prompts WHERE role = $1 ORDER BY version ASC;`,
      ['issue-analysis-agent'],
    );
    expect(rolePrompts.rows.map((r) => ({ version: r.version, is_active: r.is_active }))).toEqual([
      { version: 1, is_active: false },
      { version: 2, is_active: true },
    ]);

    await request(app)
      .post(`/prompt-updates/${promptUpdateId}/review`)
      .send({ action: 'approve' })
      .set('Content-Type', 'application/json')
      .expect(409);

    await request(app)
      .post(`/prompt-updates/${promptUpdateId}/apply`)
      .send({})
      .set('Content-Type', 'application/json')
      .expect(409);
  });
});
