# Postgres KB Quickstart (Local install + pgvector)

목표: `raw/**/raw_http/**.json`에서 Closed Issue/PR을 추출해 Postgres에 적재하고, 검색 단위(`kb_document`)를 생성한다.

## 1) Postgres 설치 (Homebrew)

```bash
brew install postgresql@17 pgvector
brew services start postgresql@17
```

## 2) raw_http → 뷰(CSV) → Postgres → kb_document

```bash
RAW_DIR="raw/openai-openai-agents-python/closedAt_2026-01-06_2026-01-20_20260120T045252Z/raw_http"
python3 scripts/pg_kb_bootstrap_local.py --raw-http-dir "$RAW_DIR"
```

이 스크립트는 다음을 수행한다.
- `scripts/export_repo_work_item_views.py`로 `out_views/*.csv` 생성(본문은 excerpt로 제한)
- `sql/001_schema.sql`로 테이블 생성(`repo_*`, `kb_document`, `kb_embedding`)
- `psql \\copy`로 `repo_*` 적재(`out_views/*.csv`)
- `sql/003_build_kb_documents.sql`로 `kb_document` upsert

## 3) 확인/검색(예시)

```bash
psql -d prism_phase1 -c "select count(*) from kb_document;"
```

키워드 검색(FTS):
```bash
psql -d prism_phase1 -c "select item_type,item_number,section,source_ref from kb_document where text_tsv @@ plainto_tsquery('simple','mcp') limit 10;"
```

## 4) 임베딩 벡터 적재(스키마만 준비)

## 4) 임베딩 벡터 적재(OpenAI `text-embedding-3-large`)

1) 환경변수 설정:
```bash
export OPENAI_API_KEY="..."
```

2) 임베딩 생성/업서트:
```bash
python3 scripts/embed_kb_documents_openai.py --db-name prism_phase1 --db-user "$USER" --model text-embedding-3-large --dimensions 3072
```

3) 확인:
```bash
psql -d prism_phase1 -c "select count(*) from kb_embedding where model='text-embedding-3-large';"
```

## (옵션) Docker로 실행

로컬 설치가 어려운 환경에서는 `docker-compose.postgres.yml`로도 동일한 스키마를 올릴 수 있다.
