-- Prism Phase 3 (Retrospective Court) storage schema (MVP).
-- Safe defaults:
-- - Store redacted-only data (enforced in application layer).
-- - Use UUID primary keys (pgcrypto).
-- - `case_events.ingested_at` automatically recorded.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
  EXCEPTION
    WHEN undefined_file THEN
      RAISE NOTICE 'pgvector extension not installed; lessons.embedding will use float8[] fallback.';
  END;
END $$;

CREATE TABLE IF NOT EXISTS cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  source jsonb NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  redaction_policy_version text,
  summary text,
  status text NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS court_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  model text,
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  status text NOT NULL DEFAULT 'running',
  artifacts jsonb
);

CREATE TABLE IF NOT EXISTS case_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  court_run_id uuid REFERENCES court_runs(id) ON DELETE SET NULL,
  ts timestamptz,
  seq bigint,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  actor_type text,
  actor_id text,
  role text,
  event_type text NOT NULL,
  content text,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  usage jsonb
);

DO $$
BEGIN
  IF to_regtype('vector') IS NOT NULL THEN
    EXECUTE $sql$
      CREATE TABLE IF NOT EXISTS lessons (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        role text NOT NULL,
        polarity text CHECK (polarity IN ('do', 'dont')),
        title text,
        content text NOT NULL,
        rationale text,
        confidence real,
        tags text[],
        evidence_event_ids uuid[],
        embedding vector,
        embedding_model text,
        embedding_dim integer,
        created_at timestamptz NOT NULL DEFAULT now(),
        supersedes_lesson_id uuid REFERENCES lessons(id) ON DELETE SET NULL
      );
    $sql$;
  ELSE
    EXECUTE $sql$
      CREATE TABLE IF NOT EXISTS lessons (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        role text NOT NULL,
        polarity text CHECK (polarity IN ('do', 'dont')),
        title text,
        content text NOT NULL,
        rationale text,
        confidence real,
        tags text[],
        evidence_event_ids uuid[],
        embedding double precision[],
        embedding_model text,
        embedding_dim integer,
        created_at timestamptz NOT NULL DEFAULT now(),
        supersedes_lesson_id uuid REFERENCES lessons(id) ON DELETE SET NULL
      );
    $sql$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS judgements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  court_run_id uuid REFERENCES court_runs(id) ON DELETE SET NULL,
  decision jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role text NOT NULL,
  version integer NOT NULL,
  prompt text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  is_active boolean NOT NULL DEFAULT false,
  UNIQUE (role, version)
);

-- At most one active prompt per role.
CREATE UNIQUE INDEX IF NOT EXISTS uniq_role_prompts_active_per_role
  ON role_prompts(role)
  WHERE is_active;

CREATE TABLE IF NOT EXISTS prompt_updates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid REFERENCES cases(id) ON DELETE SET NULL,
  agent_id text,
  role text NOT NULL,
  from_version integer,
  proposal text NOT NULL,
  reason text,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'approved', 'applied', 'rejected')),
  review_comment text,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  approved_by text,
  applied_at timestamptz
);

CREATE TABLE IF NOT EXISTS redaction_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version text NOT NULL,
  policy jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  is_active boolean NOT NULL DEFAULT false,
  UNIQUE (version)
);

-- At most one active policy (optional).
CREATE UNIQUE INDEX IF NOT EXISTS uniq_redaction_policies_active
  ON redaction_policies(is_active)
  WHERE is_active;

-- Recommended indexes for timeline and review workflows.
CREATE INDEX IF NOT EXISTS idx_case_events_case_ts ON case_events(case_id, ts);
CREATE INDEX IF NOT EXISTS idx_case_events_case_seq ON case_events(case_id, seq);
CREATE INDEX IF NOT EXISTS idx_prompt_updates_status_created_at ON prompt_updates(status, created_at);
CREATE INDEX IF NOT EXISTS idx_lessons_role ON lessons(role);

