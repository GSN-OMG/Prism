# Prism

Codex CLI를 활용해 빠르게 구현/검증/데모까지 가져가기 위한 해커톤용 워크스페이스입니다.

## 빠른 시작

- Codex 실행: `codex`
- 변경사항 리뷰: `codex review --uncommitted`
- 재사용 프롬프트 실행: `codex exec - < .codex/prompts/plan.md`
- (선택) 공통 커맨드: `make help`

## 추천 워크플로우 (해커톤)

1. 계획: `.codex/prompts/plan.md`
2. 구현: `.codex/prompts/implement.md`
3. 리뷰: `.codex/prompts/review.md` / `.codex/prompts/code-review.md`
4. 보안 점검(필요 시): `.codex/prompts/security-review.md`
5. 빌드 깨짐/타입 에러: `.codex/prompts/build-fix.md`
6. 데모 준비: `.codex/prompts/demo-script.md`

## 문서/템플릿

- Codex 작업 규칙(프로젝트용): `CODEX.md`
- 해커톤 플레이북: `docs/hackathon-playbook.md`
- ADR 템플릿(설계 결정 기록): `docs/adr-template.md`

## Phase 3 (Retrospective Court)

- 레댁션 파이프라인 테스트: `PYTHONPATH=src python3 -m unittest tests.test_redaction_pipeline`
- JSON 레댁션 실행(디폴트 정책): `PYTHONPATH=src python3 -m prism.phase3.redaction_pipeline --report < input.json > redacted.json`
- GitHub 컨텍스트 번들 생성: `PYTHONPATH=src GITHUB_REPO=owner/repo GITHUB_TYPE=pull_request GITHUB_NUMBER=42 python3 -m prism.phase3.github_context_builder --out /tmp/context-bundle.json`
- 교훈 임베딩 검색(Top-K): `PYTHONPATH=src DATABASE_URL=... PRISM_EMBEDDING_MODEL=... python3 -m prism.phase3.embeddings_and_search search-lessons --role coder --query "..." --k 5`
- (선택) pgvector 인덱스 생성: `PYTHONPATH=src DATABASE_URL=... python3 -m prism.phase3.embeddings_and_search create-index`

## Phase 3: GUI (리뷰 + 타임라인) (MVP)

`phase3/specs/07-gui-review-timeline.md` 구현물은 Node/Express 서버로 제공합니다.

- 설치: `make setup` (또는 `npm install`)
- 실행(인메모리 DB + 데모 시드 자동): `npm run dev`
- 실행(Postgres): `DATABASE_URL=postgresql://... npm run dev`
  - (선택) 데모 시드: `SEED_DEMO_DATA=true DATABASE_URL=... npm run dev`
- 접속: `http://localhost:3000/gui`

### API (JSON)

- `GET /cases`
- `GET /cases/:id`
- `GET /cases/:id/events?actor_type=&actor_id=&role=&event_type=&stage=`
- `GET /cases/:id/court-runs`
- `GET /prompt-updates?case_id=&status=proposed`
- `POST /prompt-updates/:id/review` (`action=approve|reject`, `comment?`, `reviewer?`)
- `POST /prompt-updates/:id/apply`

## 참고

이 레포의 Codex 템플릿/체크리스트 구성은 `affaan-m/everything-claude-code`의 아이디어를 Codex CLI 워크플로우에 맞게 재구성한 것입니다.

## Phase 3: PostgreSQL 스토리지(MVP)

`phase3/specs/03-postgres-storage.md` 구현물은 Python 모듈로 제공됩니다.

- 설치: `make setup`
- 마이그레이션: `DATABASE_URL=... python3 -m prism.storage.migrate`
- 코드 사용: `src/prism/storage/postgres.py`의 `PostgresStorage` (입력은 redacted-only)

## Phase 3: Prompt Registry + HITL (MVP)

- GUI에서 Judge 권고안(`prompt_updates`)을 `approve/reject`로 리뷰한다.
- 승인된 권고안만 `apply` 가능:
  - 새 `role_prompts` 버전 생성 + `is_active=true` (기존 active는 비활성화)
  - `prompt_updates.status=applied`, `applied_at` 기록
