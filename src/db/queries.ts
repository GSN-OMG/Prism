import { randomUUID } from 'node:crypto';
import type { Pool } from 'pg';
import { assertNoSensitiveData } from '../redaction/index.js';

export type CaseRow = {
  id: string;
  created_at: Date;
  source: unknown;
  metadata: unknown;
  summary: string | null;
  status: string | null;
  redaction_policy_version: string | null;
};

export type CourtRunRow = {
  id: string;
  case_id: string;
  model: string | null;
  started_at: Date;
  ended_at: Date | null;
  status: string;
  artifacts: unknown;
};

export type CaseEventRow = {
  id: number;
  case_id: string;
  ts: Date | null;
  seq: string | number | null;
  ingested_at: Date;
  actor_type: string;
  actor_id: string | null;
  role: string | null;
  event_type: string;
  content: string;
  meta: unknown;
  court_run_id: string | null;
};

export type PromptUpdateRow = {
  id: string;
  case_id: string;
  agent_id: string | null;
  role: string;
  from_version: number | null;
  proposal: unknown;
  reason: string | null;
  status: string;
  created_at: Date;
  approved_at: Date | null;
  applied_at: Date | null;
  approved_by: string | null;
  review_comment: string | null;
};

export type RolePromptRow = {
  id: string;
  role: string;
  version: number;
  prompt: string;
  created_at: Date;
  is_active: boolean;
};

function extractProposedPrompt(proposal: unknown): string | null {
  if (typeof proposal === 'string') return proposal;
  if (!proposal || typeof proposal !== 'object') return null;
  const obj = proposal as Record<string, unknown>;
  for (const key of ['prompt', 'full_prompt', 'fullPrompt']) {
    const value = obj[key];
    if (typeof value === 'string') return value;
  }
  return null;
}

export async function listCasesWithLatestRun(pool: Pool): Promise<
  Array<
    CaseRow & {
      latest_court_run:
        | (Pick<CourtRunRow, 'id' | 'status' | 'started_at' | 'ended_at' | 'model'> & {
            id: string;
          })
        | null;
    }
  >
> {
  const result = await pool.query<{
    id: string;
    created_at: Date;
    source: unknown;
    metadata: unknown;
    summary: string | null;
    status: string | null;
    redaction_policy_version: string | null;
    latest_run_id: string | null;
    latest_run_status: string | null;
    latest_run_started_at: Date | null;
    latest_run_ended_at: Date | null;
    latest_run_model: string | null;
  }>(
    `
    SELECT
      c.*,
      cr.id AS latest_run_id,
      cr.status AS latest_run_status,
      cr.started_at AS latest_run_started_at,
      cr.ended_at AS latest_run_ended_at,
      cr.model AS latest_run_model
    FROM cases c
    LEFT JOIN (
      SELECT case_id, MAX(started_at) AS max_started_at
      FROM court_runs
      GROUP BY case_id
    ) latest ON latest.case_id = c.id
    LEFT JOIN court_runs cr
      ON cr.case_id = c.id AND cr.started_at = latest.max_started_at
    ORDER BY c.created_at DESC;
    `,
  );

  return result.rows.map((row) => ({
    id: row.id,
    created_at: row.created_at,
    source: row.source,
    metadata: row.metadata,
    summary: row.summary,
    status: row.status,
    redaction_policy_version: row.redaction_policy_version,
    latest_court_run: row.latest_run_id
      ? {
          id: row.latest_run_id,
          status: row.latest_run_status ?? 'unknown',
          started_at: row.latest_run_started_at ?? new Date(0),
          ended_at: row.latest_run_ended_at,
          model: row.latest_run_model,
        }
      : null,
  }));
}

export async function getCaseById(pool: Pool, caseId: string): Promise<CaseRow | null> {
  const result = await pool.query<CaseRow>(`SELECT * FROM cases WHERE id = $1;`, [caseId]);
  return result.rows[0] ?? null;
}

export type ListEventsFilters = Partial<{
  actor_type: string;
  actor_id: string;
  role: string;
  event_type: string;
  stage: string;
}>;

export async function listCaseEvents(
  pool: Pool,
  caseId: string,
  filters: ListEventsFilters,
): Promise<CaseEventRow[]> {
  const conditions: string[] = ['case_id = $1'];
  const params: Array<string> = [caseId];

  const addFilter = (sql: string, value: string | undefined) => {
    if (!value) return;
    params.push(value);
    conditions.push(sql.replaceAll('$X', `$${params.length}`));
  };

  addFilter(`actor_type = $X`, filters.actor_type);
  addFilter(`actor_id = $X`, filters.actor_id);
  addFilter(`role = $X`, filters.role);
  addFilter(`event_type = $X`, filters.event_type);
  addFilter(`meta->>'stage' = $X`, filters.stage);

  const result = await pool.query<CaseEventRow>(
    `
    SELECT *
    FROM case_events
    WHERE ${conditions.join(' AND ')}
    ORDER BY ts NULLS LAST, seq NULLS LAST, id ASC;
    `,
    params,
  );

  return result.rows;
}

export async function listCourtRuns(pool: Pool, caseId: string): Promise<CourtRunRow[]> {
  const result = await pool.query<CourtRunRow>(
    `SELECT * FROM court_runs WHERE case_id = $1 ORDER BY started_at DESC;`,
    [caseId],
  );
  return result.rows;
}

export async function listPromptUpdates(
  pool: Pool,
  opts: { caseId?: string; status?: string },
): Promise<PromptUpdateRow[]> {
  const conditions: string[] = [];
  const params: Array<string> = [];
  if (opts.caseId) {
    params.push(opts.caseId);
    conditions.push(`case_id = $${params.length}`);
  }
  if (opts.status) {
    params.push(opts.status);
    conditions.push(`status = $${params.length}`);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const result = await pool.query<PromptUpdateRow>(
    `
    SELECT *
    FROM prompt_updates
    ${where}
    ORDER BY created_at DESC;
    `,
    params,
  );
  return result.rows;
}

export async function getRolePrompt(
  pool: Pool,
  role: string,
  version: number,
): Promise<RolePromptRow | null> {
  const result = await pool.query<RolePromptRow>(
    `SELECT * FROM role_prompts WHERE role = $1 AND version = $2 LIMIT 1;`,
    [role, version],
  );
  return result.rows[0] ?? null;
}

export async function getActiveRolePrompt(pool: Pool, role: string): Promise<RolePromptRow | null> {
  const result = await pool.query<RolePromptRow>(
    `SELECT * FROM role_prompts WHERE role = $1 AND is_active = true ORDER BY version DESC LIMIT 1;`,
    [role],
  );
  return result.rows[0] ?? null;
}

export async function reviewPromptUpdate(
  pool: Pool,
  promptUpdateId: string,
  action: 'approve' | 'reject',
  opts: { comment?: string; approvedBy?: string },
): Promise<PromptUpdateRow> {
  assertNoSensitiveData({
    review_comment: opts.comment ?? null,
    approved_by: opts.approvedBy ?? null,
  });

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const existing = await client.query<PromptUpdateRow>(
      `SELECT * FROM prompt_updates WHERE id = $1 FOR UPDATE;`,
      [promptUpdateId],
    );
    const row = existing.rows[0];
    if (!row) {
      throw new Error('NOT_FOUND');
    }
    if (row.status !== 'proposed') {
      throw new Error('INVALID_STATUS');
    }

    const newStatus = action === 'approve' ? 'approved' : 'rejected';
    const approvedAt = action === 'approve' ? new Date() : null;
    const updated = await client.query<PromptUpdateRow>(
      `
      UPDATE prompt_updates
      SET
        status = $2,
        approved_at = $3,
        approved_by = $4,
        review_comment = $5
      WHERE id = $1
      RETURNING *;
      `,
      [promptUpdateId, newStatus, approvedAt, opts.approvedBy ?? null, opts.comment ?? null],
    );
    await client.query('COMMIT');
    return updated.rows[0] as PromptUpdateRow;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

export async function applyPromptUpdate(
  pool: Pool,
  promptUpdateId: string,
): Promise<{ rolePrompt: RolePromptRow; promptUpdate: PromptUpdateRow }> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const existing = await client.query<PromptUpdateRow>(
      `SELECT * FROM prompt_updates WHERE id = $1 FOR UPDATE;`,
      [promptUpdateId],
    );
    const update = existing.rows[0];
    if (!update) {
      throw new Error('NOT_FOUND');
    }
    if (update.status !== 'approved') {
      throw new Error('INVALID_STATUS');
    }

    const proposedPrompt = extractProposedPrompt(update.proposal);
    if (!proposedPrompt) {
      throw new Error('INVALID_PROPOSAL');
    }
    assertNoSensitiveData({ prompt: proposedPrompt });

    await client.query(`SELECT id FROM role_prompts WHERE role = $1 FOR UPDATE;`, [update.role]);

    const maxVersionResult = await client.query<{ max_version: number }>(
      `SELECT COALESCE(MAX(version), 0)::int AS max_version FROM role_prompts WHERE role = $1;`,
      [update.role],
    );

    const maxVersion = maxVersionResult.rows[0]?.max_version ?? 0;
    const baseVersion = maxVersion;

    if (typeof update.from_version === 'number' && update.from_version !== baseVersion) {
      throw new Error('FROM_VERSION_MISMATCH');
    }

    const newVersion = maxVersion + 1;
    const newRolePromptId = randomUUID();

    const inserted = await client.query<RolePromptRow>(
      `
      INSERT INTO role_prompts (id, role, version, prompt, is_active)
      VALUES ($1, $2, $3, $4, true)
      RETURNING *;
      `,
      [newRolePromptId, update.role, newVersion, proposedPrompt],
    );

    await client.query(
      `
      UPDATE role_prompts
      SET is_active = false
      WHERE role = $1 AND id <> $2 AND is_active = true;
      `,
      [update.role, newRolePromptId],
    );

    const updated = await client.query<PromptUpdateRow>(
      `
      UPDATE prompt_updates
      SET status = 'applied',
          applied_at = now()
      WHERE id = $1
      RETURNING *;
      `,
      [promptUpdateId],
    );

    await client.query('COMMIT');
    return {
      rolePrompt: inserted.rows[0] as RolePromptRow,
      promptUpdate: updated.rows[0] as PromptUpdateRow,
    };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}
