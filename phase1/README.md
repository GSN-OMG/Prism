# Prism Phase 1: GitHub raw_http → Postgres KB (+ OpenAI embeddings)

This folder contains lightweight, standard-library Python scripts to:
1) ingest GitHub REST/GraphQL responses as **raw HTTP JSON** (`raw_http/`),  
2) export relational-friendly views (CSV),  
3) load **Closed** Issue/PR metadata into Postgres,  
4) build a searchable KB (`kb_document`) and store embeddings (`kb_embedding`) using OpenAI.

## What you get

- `raw/**/raw_http/**.json`: source-of-truth snapshots (immutable)
- `out_views/*.csv`: thin relational views for Postgres loading
- Postgres tables:
  - `repo_work_item`, `repo_comment`, `repo_pr_review`, `repo_work_item_event`
  - `kb_document`: search units (chunked, bounded text + metadata + source links)
  - `kb_embedding`: OpenAI embedding vectors for `kb_document`

## Prerequisites

- Python 3 (`python3`)
- macOS + Homebrew (recommended for local Postgres)
- GitHub token for ingestion (unless discovery-only):
  - `GITHUB_TOKEN` or `GH_TOKEN`
- OpenAI API key for embeddings:
  - `OPENAI_API_KEY`

## Quickstart

### 1) Ingest raw_http (ClosedAt window)

```bash
export GITHUB_TOKEN="..."
python3 scripts/github_raw_ingest_closedat.py --start 2026-01-06 --end 2026-01-20
```

The script writes a new run folder under:
- `raw/openai-openai-agents-python/closedAt_<start>_<end>_<timestamp>/raw_http/...`

### 2) Install local Postgres + pgvector (Homebrew)

```bash
brew install postgresql@17 pgvector
brew services start postgresql@17
```

`postgresql@17` is keg-only. If `psql` is not found:
```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
```

### 3) Build Postgres KB (views → tables → kb_document)

```bash
RAW_DIR="raw/openai-openai-agents-python/closedAt_2026-01-06_2026-01-20_20260120T045252Z/raw_http"
python3 scripts/pg_kb_bootstrap_local.py --raw-http-dir "$RAW_DIR" --db-user "$USER" --db-name prism_phase1
```

Verify:
```bash
psql -d prism_phase1 -c "select count(*) from kb_document;"
```

### 4) Create OpenAI embeddings (text-embedding-3-large)

```bash
export OPENAI_API_KEY="..."
python3 scripts/embed_kb_documents_openai.py --db-name prism_phase1 --db-user "$USER" --model text-embedding-3-large --dimensions 3072
```

Verify:
```bash
psql -d prism_phase1 -c "select model, count(*) from kb_embedding group by model;"
```

## Search examples

### Keyword search (FTS)

```bash
psql -d prism_phase1 -c \
"select item_type,item_number,section,source_ref from kb_document where text_tsv @@ plainto_tsquery('simple','mcp') limit 20;"
```

### Vector search (pgvector)

This requires you to generate an embedding for your query text with the same model
(`text-embedding-3-large`) and pass it as a vector literal.

Example shape:
```sql
SELECT
  d.item_type, d.item_number, d.section, d.source_ref
FROM kb_embedding e
JOIN kb_document d ON d.kb_id = e.kb_id
WHERE e.model = 'text-embedding-3-large'
ORDER BY e.embedding <-> '[0.01, -0.02, ...]'::vector
LIMIT 20;
```

## Notes / conventions

- Actor identifiers are exported as GitHub-style user ids, e.g. `@mattlgroff`.
- Do not commit `raw/` or `out_*` outputs; they are generated artifacts.
- `raw_http` is treated as immutable source-of-truth; fix scripts and re-export/re-ingest instead of editing raw data.

## Related docs

- ETL/collection design: `docs/openai-agents-python-closedAt-2w-etl-spec.md`
- Prompt refiner agent spec: `docs/openai-agents-python-prompt-refiner-agent-spec.md`
- Postgres KB quickstart: `docs/postgres_kb_quickstart.md`

## Tests

```bash
python3 -m unittest discover -s tests -q
python3 -m py_compile scripts/*.py
```

