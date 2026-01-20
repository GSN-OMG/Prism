# scripts

## github_raw_ingest_closedat.py

GitHub API(REST + GraphQL)를 호출해서 **closedAt 기준 기간 내 PR/Issue의 raw 응답만** `raw/` 아래에 저장합니다.  
정규화/RDB 적재/요약/벡터화 등 데이터 처리는 수행하지 않습니다.

### Prereq

- 전체(Discovery + Hydration) 수집: `GITHUB_TOKEN` 또는 `GH_TOKEN` 환경변수에 GitHub 토큰 설정
- Discovery-only(검색 결과 raw 저장만): 토큰 없이도 가능(`--no-hydrate`)
  - 참고: 토큰은 raw 저장 시 기록하지 않으며, `curl` 호출 시에도 argv에 토큰이 노출되지 않도록 `-H @file` 방식으로 전달합니다.

### Example

```bash
python3 scripts/github_raw_ingest_closedat.py --start 2026-01-06 --end 2026-01-20
```

## export_repo_work_item_views.py

`raw_http/**.json`에서 Issue/PR/타임라인/댓글/리뷰를 “얇은” 관계형 뷰(CSV)로 내보냅니다.  
본문/댓글 전문을 그대로 프롬프트에 넣지 않도록, 댓글/리뷰는 `body_excerpt`만(기본 280자) 저장합니다.

```bash
python3 scripts/export_repo_work_item_views.py --raw-http-dir raw/.../raw_http --out-dir out_views
```

## build_repo_insights.py

`raw_http/**.json`에서 **bounded** `repo_insights.json/.md`를 생성합니다(카드 수/문장 길이/근거 개수에 캡이 있어 컨텍스트 폭발을 방지).

```bash
python3 scripts/build_repo_insights.py --raw-http-dir raw/.../raw_http --out-dir out_insights
```

## generate_prompt_updates_from_insights.py

`AGENTS_SUMMARY.md` + `repo_insights.json`을 입력으로, 에이전트별 시스템 프롬프트 초안을 생성합니다(현재 프롬프트 뒤에 Repo-Specific Context 블록을 append).

```bash
python3 scripts/generate_prompt_updates_from_insights.py \\
  --agents-summary AGENTS_SUMMARY.md \\
  --repo-insights out_insights/repo_insights.json \\
  --out-dir out_prompts
```

## Postgres KB (Docker)

This repo can run a local Postgres + pgvector instance via Homebrew and load derived views into relational tables,
then build `kb_document` records for search (Closed Issue/PR only).

```bash
RAW_DIR="raw/.../raw_http"
brew install postgresql@17 pgvector
brew services start postgresql@17
python3 scripts/pg_kb_bootstrap_local.py --raw-http-dir "$RAW_DIR"
```

Optional Docker fallback:
```bash
docker compose -f docker-compose.postgres.yml up -d
python3 scripts/pg_kb_bootstrap_docker.py --raw-http-dir "$RAW_DIR"
```

## embed_kb_documents_openai.py

Generate OpenAI embeddings for `kb_document` and upsert into `kb_embedding`.

```bash
export OPENAI_API_KEY="..."
python3 scripts/embed_kb_documents_openai.py --db-name prism_phase1 --db-user "$USER" --model text-embedding-3-large --dimensions 3072
```
