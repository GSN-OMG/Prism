CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS repo_work_item (
  repo_full_name TEXT NOT NULL,
  number INTEGER NOT NULL,
  type TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  body_excerpt TEXT NULL,
  state TEXT NOT NULL,
  created_at TIMESTAMPTZ NULL,
  closed_at TIMESTAMPTZ NULL,
  author_login TEXT NULL,
  author_association TEXT NULL,
  labels_json JSONB NOT NULL,
  milestone_title TEXT NULL,
  is_merged BOOLEAN NOT NULL,
  merged_at TIMESTAMPTZ NULL,
  merged_by TEXT NULL,
  comment_count INTEGER NULL,
  review_count INTEGER NULL,
  changed_files INTEGER NULL,
  additions INTEGER NULL,
  deletions INTEGER NULL,
  PRIMARY KEY (repo_full_name, number, type)
);

CREATE TABLE IF NOT EXISTS repo_work_item_event (
  repo_full_name TEXT NOT NULL,
  number INTEGER NOT NULL,
  type TEXT NOT NULL,
  event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  actor_login TEXT NULL,
  subject_type TEXT NULL,
  subject TEXT NULL,
  reference TEXT NOT NULL,
  PRIMARY KEY (repo_full_name, number, type, event_id)
);

CREATE TABLE IF NOT EXISTS repo_comment (
  repo_full_name TEXT NOT NULL,
  number INTEGER NOT NULL,
  type TEXT NOT NULL,
  comment_id TEXT NOT NULL,
  url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  author_login TEXT NULL,
  author_association TEXT NULL,
  body_excerpt TEXT NULL,
  PRIMARY KEY (repo_full_name, number, type, comment_id)
);

CREATE TABLE IF NOT EXISTS repo_pr_review (
  repo_full_name TEXT NOT NULL,
  pr_number INTEGER NOT NULL,
  review_id TEXT NOT NULL,
  review_state TEXT NULL,
  submitted_at TIMESTAMPTZ NOT NULL,
  author_login TEXT NULL,
  body_excerpt TEXT NULL,
  reference TEXT NOT NULL,
  PRIMARY KEY (repo_full_name, pr_number, review_id)
);

ALTER TABLE repo_work_item
  ALTER COLUMN body_excerpt DROP NOT NULL,
  ALTER COLUMN author_login DROP NOT NULL,
  ALTER COLUMN author_association DROP NOT NULL,
  ALTER COLUMN milestone_title DROP NOT NULL,
  ALTER COLUMN merged_by DROP NOT NULL;

ALTER TABLE repo_work_item_event
  ALTER COLUMN actor_login DROP NOT NULL,
  ALTER COLUMN subject_type DROP NOT NULL,
  ALTER COLUMN subject DROP NOT NULL;

ALTER TABLE repo_comment
  ALTER COLUMN author_login DROP NOT NULL,
  ALTER COLUMN author_association DROP NOT NULL,
  ALTER COLUMN body_excerpt DROP NOT NULL;

ALTER TABLE repo_pr_review
  ALTER COLUMN review_state DROP NOT NULL,
  ALTER COLUMN author_login DROP NOT NULL,
  ALTER COLUMN body_excerpt DROP NOT NULL;

CREATE TABLE IF NOT EXISTS kb_document (
  kb_id TEXT PRIMARY KEY,
  repo_full_name TEXT NOT NULL,
  item_type TEXT NOT NULL,
  item_number INTEGER NOT NULL,
  section TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  closed_at TIMESTAMPTZ NULL,
  text TEXT NOT NULL,
  metadata JSONB NOT NULL,
  source_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE kb_document
  ADD COLUMN IF NOT EXISTS text_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED;

CREATE TABLE IF NOT EXISTS kb_embedding (
  kb_id TEXT NOT NULL REFERENCES kb_document(kb_id) ON DELETE CASCADE,
  model TEXT NOT NULL,
  dims INTEGER NOT NULL,
  embedding vector(3072) NOT NULL,
  source_hash TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (kb_id, model)
);

ALTER TABLE kb_embedding
  ADD COLUMN IF NOT EXISTS source_hash TEXT NOT NULL DEFAULT '';

-- Migrate older schemas (e.g., vector(1536)) to text-embedding-3-large default (3072 dims).
ALTER TABLE kb_embedding
  ALTER COLUMN embedding TYPE vector(3072);

CREATE INDEX IF NOT EXISTS idx_repo_work_item_closed_at
  ON repo_work_item (repo_full_name, closed_at);

CREATE INDEX IF NOT EXISTS idx_kb_document_lookup
  ON kb_document (repo_full_name, item_type, item_number, section);

CREATE INDEX IF NOT EXISTS idx_kb_document_tsv
  ON kb_document USING GIN (text_tsv);
