# Repository Guidelines

This repository contains lightweight, standard-library Python scripts for ingesting GitHub REST/GraphQL responses as **raw HTTP JSON** and exporting simplified, relational-friendly views, bounded “insight packs”, and a Postgres KB (e.g., `repo_user`, `repo_user_activity`, `repo_work_item`, `repo_insights`, `kb_document`, `kb_embedding`).

## Project Structure & Module Organization

- `scripts/`: CLI scripts.
  - `scripts/github_raw_ingest_closedat.py`: fetches raw responses into `raw/`.
  - `scripts/export_repo_user_activity_csv.py`: derives CSVs from `raw/**/raw_http/**.json`.
  - `scripts/export_repo_work_item_views.py`: derives work-item relational views (`repo_work_item`, `repo_work_item_event`, `repo_comment`, `repo_pr_review`) from `raw/**/raw_http/**.json`.
  - `scripts/build_repo_insights.py`: builds **bounded** `repo_insights.json/.md` from `raw/**/raw_http/**.json` (caps cards/statement length/evidence count to prevent context blow-ups).
  - `scripts/generate_prompt_updates_from_insights.py`: generates per-agent prompt drafts from `AGENTS_SUMMARY.md` + `repo_insights.json`.
  - `scripts/pg_kb_bootstrap_local.py`: exports views, loads Postgres tables, and builds `kb_document` (local Postgres).
  - `scripts/embed_kb_documents_openai.py`: generates OpenAI embeddings and upserts into `kb_embedding`.
- `raw/`: generated ingestion outputs. Typical layout:
  - `raw/<owner>-<repo>/closedAt_<start>_<end>_<timestamp>/raw_http/<tag>/*.json`
- `tests/`: `unittest`-based regression tests.
- `docs/`: design notes/specs.
- `AGENTS_SUMMARY.md`: input spec for agent system prompts (used to generate updated prompt drafts).
- `out_*`: generated exports (don’t treat as source).

## Build, Test, and Development Commands

- Ingest raw responses (token required unless discovery-only):
  - `GITHUB_TOKEN=... python3 scripts/github_raw_ingest_closedat.py --start 2026-01-06 --end 2026-01-20`
  - Discovery-only (no token): `python3 scripts/github_raw_ingest_closedat.py --no-hydrate ...`
- Export CSVs from an existing `raw_http` directory:
  - `python3 scripts/export_repo_user_activity_csv.py --raw-http-dir raw/.../raw_http --out-dir out_export`
  - `python3 scripts/export_repo_work_item_views.py --raw-http-dir raw/.../raw_http --out-dir out_views`
- Build bounded repo insights (recommended input to prompt-refiners; do **not** feed raw_http directly):
  - `python3 scripts/build_repo_insights.py --raw-http-dir raw/.../raw_http --out-dir out_insights --max-cards 30 --max-evidence 5 --max-statement-chars 240`
- Generate per-agent prompt drafts (LLM-based; OpenAI):
  - `OPENAI_API_KEY=... python3 scripts/generate_prompt_updates_from_insights.py --agents-summary AGENTS_SUMMARY.md --repo-insights out_insights/repo_insights.json --out-dir out_prompts --max-cards-per-agent 15`
- Run tests:
  - `python3 -m unittest discover -s tests -q`
- Quick syntax check:
  - `python3 -m py_compile scripts/*.py`

## Postgres (KB) Commands

- Install locally (Homebrew):
  - `brew install postgresql@17 pgvector`
  - `brew services start postgresql@17`
  - If `psql` is not found: `export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"`
- Bootstrap KB tables from an existing `raw_http` directory (exports views → loads into DB → builds `kb_document`):
  - `python3 scripts/pg_kb_bootstrap_local.py --raw-http-dir raw/.../raw_http --db-name prism_phase1 --db-user "$USER"`
- Inspect counts:
  - `psql -d prism_phase1 -c "select count(*) from kb_document;"`
- Embed `kb_document` into `kb_embedding` (OpenAI):
  - `OPENAI_API_KEY=... python3 scripts/embed_kb_documents_openai.py --db-name prism_phase1 --db-user "$USER" --model text-embedding-3-large --dimensions 3072`
- Optional Docker fallback:
  - `docker compose -f docker-compose.postgres.yml up -d`
  - `python3 scripts/pg_kb_bootstrap_docker.py --raw-http-dir raw/.../raw_http`

## Coding Style & Naming Conventions

- Python: 4-space indentation, keep changes PEP8-ish and consistent with existing files.
- Prefer the standard library (no DB drivers required); scripts should run with `python3` only.
- Use `snake_case` for filenames and functions.

## Testing Guidelines

- Framework: `unittest` in `tests/`.
- Add/extend tests when changing parsing rules (e.g., new event mappings, label extraction, bounded insight caps).
- Test file naming: `tests/test_*.py`.

## Commit & Pull Request Guidelines

- History is minimal; use short, imperative commit subjects (e.g., “fix exporter role mapping”).
- PRs should include: what changed, which `raw_http` tags/paths were used for validation, and the exact test command run.

## Security & Configuration Tips

- Tokens must come from `GITHUB_TOKEN`/`GH_TOKEN`; do not hardcode secrets or write them to `raw/`.
- OpenAI credentials must come from `OPENAI_API_KEY`; do not hardcode secrets or commit `.env` files.
- Treat `raw_http` as source-of-truth inputs; avoid “fixing” data in-place—fix scripts and re-export/re-ingest instead.
- Context safety: never dump raw `body`/full comment threads into system prompts; use bounded `repo_insights.json` + evidence URLs and fetch specifics on-demand.
- Identity conventions: actor ids are exported as GitHub-style `user_id` strings like `@mattlgroff` (no numeric/node-id fallback).
