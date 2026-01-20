export const schemaStatements = [
  `
  CREATE TABLE IF NOT EXISTS cases (
    id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    source jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    summary text,
    status text,
    redaction_policy_version text
  );
  `,
  `
  CREATE TABLE IF NOT EXISTS court_runs (
    id uuid PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    model text,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    status text NOT NULL,
    artifacts jsonb NOT NULL DEFAULT '{}'::jsonb
  );
  `,
  `
  CREATE TABLE IF NOT EXISTS case_events (
    id bigserial PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    ts timestamptz,
    seq bigint,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    actor_type text NOT NULL,
    actor_id text,
    role text,
    event_type text NOT NULL,
    content text NOT NULL,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    court_run_id uuid REFERENCES court_runs(id) ON DELETE SET NULL
  );
  `,
  `
  CREATE TABLE IF NOT EXISTS role_prompts (
    id uuid PRIMARY KEY,
    role text NOT NULL,
    version integer NOT NULL,
    prompt text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    is_active boolean NOT NULL DEFAULT false,
    UNIQUE(role, version)
  );
  `,
  `
  CREATE TABLE IF NOT EXISTS prompt_updates (
    id uuid PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    agent_id text,
    role text NOT NULL,
    from_version integer,
    proposal jsonb NOT NULL,
    reason text,
    status text NOT NULL DEFAULT 'proposed',
    created_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz,
    applied_at timestamptz,
    approved_by text,
    review_comment text
  );
  `,
  `CREATE INDEX IF NOT EXISTS idx_case_events_case_ts ON case_events(case_id, ts);`,
  `CREATE INDEX IF NOT EXISTS idx_case_events_case_seq ON case_events(case_id, seq);`,
  `CREATE INDEX IF NOT EXISTS idx_court_runs_case_started ON court_runs(case_id, started_at);`,
  `CREATE INDEX IF NOT EXISTS idx_prompt_updates_status_created ON prompt_updates(status, created_at);`,
  `CREATE INDEX IF NOT EXISTS idx_prompt_updates_case_status_created ON prompt_updates(case_id, status, created_at);`,
];
