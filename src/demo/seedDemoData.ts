import { randomUUID } from 'node:crypto';
import type { Pool } from 'pg';

function daysAgo(days: number): Date {
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000);
}

export async function seedDemoData(pool: Pool): Promise<void> {
  const existing = await pool.query<{ count: number }>(`SELECT COUNT(*)::int AS count FROM cases;`);
  if ((existing.rows[0]?.count ?? 0) > 0) return;

  const caseId = randomUUID();
  await pool.query(
    `
    INSERT INTO cases (id, source, metadata, summary, status, redaction_policy_version)
    VALUES ($1, $2::jsonb, $3::jsonb, $4, $5, $6);
    `,
    [
      caseId,
      JSON.stringify({
        system: 'github',
        repo: 'openai/openai-agents-python',
        type: 'issue',
        number: 2314,
      }),
      JSON.stringify({
        github: { url: 'https://github.com/openai/openai-agents-python/issues/2314' },
      }),
      'OAuth token refresh failing with custom providers (redacted demo)',
      'open',
      'default',
    ],
  );

  const basePromptV1 =
    'You are an Issue Analysis Agent. Return ONLY valid JSON.\n' +
    '- Classify: bug|feature|question|documentation|other\n' +
    '- Priority: critical|high|medium|low\n' +
    '- Include: summary, needed_skills[], keywords[], needs_more_info (bool), recommended_action.';
  const rolePromptId = randomUUID();
  await pool.query(
    `
    INSERT INTO role_prompts (id, role, version, prompt, is_active)
    VALUES ($1, $2, $3, $4, $5);
    `,
    [rolePromptId, 'issue-analysis-agent', 1, basePromptV1, true],
  );

  const proposedPromptV2 =
    basePromptV1 +
    '\n\n' +
    'Additional rules:\n' +
    '- Always cite evidence_event_ids[] for each decision.\n' +
    '- Never include secrets; assume inputs are redacted.';

  const promptUpdateId = randomUUID();
  await pool.query(
    `
    INSERT INTO prompt_updates (id, case_id, agent_id, role, from_version, proposal, reason, status)
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8);
    `,
    [
      promptUpdateId,
      caseId,
      'judge',
      'issue-analysis-agent',
      1,
      JSON.stringify({
        prompt: proposedPromptV2,
        evidence_event_ids: [1, 2],
      }),
      'Add evidence linking and reinforce redaction expectations.',
      'proposed',
    ],
  );

  const courtRunId = randomUUID();
  await pool.query(
    `
    INSERT INTO court_runs (id, case_id, model, started_at, ended_at, status, artifacts)
    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb);
    `,
    [
      courtRunId,
      caseId,
      'gpt-4.1-mini',
      daysAgo(0),
      daysAgo(0),
      'success',
      JSON.stringify({
        usage: { input_tokens: 1234, output_tokens: 987, cost_usd: 0.0123 },
        prosecutor: {
          criticisms: ['Missing evidence references for priority choice.'],
          candidate_lessons: [
            {
              role: 'issue-analysis-agent',
              polarity: 'do',
              title: 'Always link claims to evidence',
              content: 'Add evidence_event_ids for each classification decision.',
              evidence_event_ids: [1, 2],
            },
          ],
        },
        defense: {
          praises: ['Output is concise and structured JSON.'],
        },
        jury: {
          observations: ['Recommendation is plausible given labels and symptom.'],
          risks: ['If inputs are redacted, avoid guessing provider specifics.'],
        },
        judge: {
          selected_lessons: [
            {
              role: 'issue-analysis-agent',
              title: 'Evidence-first',
              content: 'Include evidence_event_ids for each key claim.',
              evidence_event_ids: [1, 2],
            },
          ],
          prompt_update_proposals: [
            {
              role: 'issue-analysis-agent',
              from_version: 1,
              reason: 'Encourage evidence linkage and redaction discipline.',
            },
          ],
        },
      }),
    ],
  );

  await pool.query(
    `
    INSERT INTO case_events (case_id, ts, seq, actor_type, actor_id, role, event_type, content, meta, court_run_id)
    VALUES
      ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NULL),
      ($1, $10, $11, $12, $13, $14, $15, $16, $17::jsonb, NULL),
      ($1, $18, $19, $20, $21, $22, $23, $24, $25::jsonb, $26),
      ($1, $27, $28, $29, $30, $31, $32, $33, $34::jsonb, $26);
    `,
    [
      caseId,
      daysAgo(1),
      1,
      'human',
      'reporter',
      null,
      'message',
      'When using a custom OAuth provider, token refresh fails with 401 (redacted).',
      JSON.stringify({ stage: 'ingest' }),
      daysAgo(1),
      2,
      'tool',
      'github',
      null,
      'tool_call',
      'GET github issue + labels (redacted)',
      JSON.stringify({ stage: 'ingest', tool: 'github.getIssue' }),
      daysAgo(1),
      3,
      'ai',
      'issue-analysis-agent',
      'issue-analysis-agent',
      'model_result',
      '{"issue_type":"bug","priority":"high","summary":"Token refresh fails with 401..."}',
      JSON.stringify({
        stage: 'analysis',
        usage: { input_tokens: 420, output_tokens: 250, cost_usd: 0.0042 },
      }),
      courtRunId,
      daysAgo(0),
      4,
      'system',
      'court',
      'judge',
      'artifact',
      'Stored judge artifacts + prompt update proposal (redacted).',
      JSON.stringify({ stage: 'court', prompt_update_id: promptUpdateId }),
    ],
  );

  const caseId2 = randomUUID();
  await pool.query(
    `
    INSERT INTO cases (id, source, metadata, summary, status, redaction_policy_version, created_at)
    VALUES ($1, $2::jsonb, $3::jsonb, $4, $5, $6, $7);
    `,
    [
      caseId2,
      JSON.stringify({
        system: 'github',
        repo: 'openai/openai-agents-python',
        type: 'issue',
        number: 2315,
      }),
      JSON.stringify({
        github: { url: 'https://github.com/openai/openai-agents-python/issues/2315' },
      }),
      'How to configure Redis caching? (redacted demo)',
      'open',
      'default',
      daysAgo(2),
    ],
  );
}
