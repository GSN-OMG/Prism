# Prism — Retrospective Court (Phase 3)

GitHub Issue/PR에서 활동하는 DevRel 서브에이전트들의 “사건 기록”을 입력으로 받아, 멀티 에이전트 공방(검사/변호사/배심원/판사)을 통해 **프롬프트 개선 권고안**과 **교훈(lesson)** 을 만들고 **PostgreSQL에 축적**하는 해커톤용 MVP입니다.

중요: DB에는 **마스킹(레댁션)된 원문만 저장**합니다(원문/시크릿 저장 금지).

## 핵심 흐름 (HITL)

1. `ContextBundle`(사건 결과/컨텍스트/피드백 + 에이전트 정보) 입력 → `Case` + `CaseEvent`로 저장(레댁션 적용)
2. 회고 법정 실행(병렬: prosecutor/defense/jury → judge)
3. 판사(Judge)가 최종 권고안(`prompt_updates`)을 제안(proposed)
4. GUI에서 **판사 최종 권고안만** `approve/reject` → 승인된 것만 `apply` 가능(프롬프트 레지스트리 버전업)

## 구성요소

- Node/TypeScript (`src/`): GUI + JSON API 서버(기본은 in-memory DB, `DATABASE_URL`로 Postgres 사용 가능)
- Python (`src/prism/`): 레댁션/스토리지/임베딩 검색/법정 오케스트레이터(에이전트 런너 어댑터 지점 포함)
- Specs/정의서: 분할 스펙(`specs/`), `ContextBundle` JSON Schema, 민감정보 정의, 기본 레댁션 정책

## 빠른 시작 (GUI 데모, Postgres 없이)

요구사항: Node.js `>=20`, Python `>=3.11`

```bash
make setup
npm run dev
```

- GUI: `http://localhost:3000/gui` (in-memory DB + 데모 시드 자동)
- 테스트: `make test`

## Postgres 모드 (권장: 데이터 유지)

```bash
cp .env.example .env
# .env에서 DATABASE_URL 등을 설정 (Node 서버는 .env를 자동 로드)

python3 -m prism.storage.migrate
npm run dev
```

- (선택) 데모 데이터 시드: `npm run seed` 또는 `SEED_DEMO_DATA=true npm run dev`

## 환경 변수 (.env)

템플릿: `.env.example` (실제 키/토큰은 커밋하지 마세요)

- Node 서버는 `.env`를 자동 로드합니다. Python CLI도 대부분 `.env`를 로드하지만, 필요하면 `DATABASE_URL=... python3 -m ...` 형태로 실행할 수 있습니다.
- `DATABASE_URL` (선택): 없으면 GUI는 in-memory DB 사용
- `PORT` (선택): GUI 서버 포트(기본 3000)
- `REDACTION_POLICY_PATH` (선택): 레댁션 정책 경로(기본 `redaction-policy.default.json`)
- `GITHUB_TOKEN` (선택): GitHub 컨텍스트 수집 시 사용
- `OPENAI_API_KEY` (선택): 에이전트 런너(OpenAI Agents SDK 어댑터) 구현 시 사용
- `PRISM_EMBEDDING_MODEL` 등: model2vec 임베딩 사용 시 설정

## 입력 포맷: ContextBundle (JSON)

- 스키마: `context-bundle.schema.json`
- 기본 아이디어: “모든 것을 사건으로” 취급하고, `events[]`를 시계열로 쌓습니다. `usage`/`meta`에 토큰/지연/에러/툴콜 등 운영 정보를 넣을 수 있습니다.

## GUI / API

- Cases 목록/상세(타임라인 + 필터 + 운영정보 표시): `GET /gui`, `GET /gui/cases/:id`
- 프롬프트 권고안 리뷰/적용(HITL): `POST /prompt-updates/:id/review`, `POST /prompt-updates/:id/apply`
- JSON API는 동일 리소스를 `/cases`, `/cases/:id/events`, `/prompt-updates` 등으로 제공합니다.

## 기능 테스트(수동)

### 1) 인메모리 데모(GUI)

```bash
make setup
cd phase3
npm run dev
```

1. `http://localhost:3000/gui` 접속 → Case 클릭
2. **Timeline**에서 이벤트를 펼쳐 `Content / Usage / Meta`가 보이는지 확인
3. **Judge prompt update review (proposed)** 에서 `Approve`
4. 아래 **approved** 섹션으로 이동했는지 확인 후 `Apply`
5. 적용 후 `prompt_updates.status=applied`, `role_prompts`가 새 버전으로 생성/활성화되는지 확인

### 2) API 스모크 테스트(curl)

서버가 켜져있다고 가정합니다(`npm run dev`).

```bash
# 1) 첫 Case / 첫 proposed prompt_update 선택
CASE_ID=$(curl -s http://localhost:3000/cases | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
PU_ID=$(curl -s "http://localhost:3000/prompt-updates?case_id=$CASE_ID&status=proposed" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 2) 레댁션 가드 확인(민감정보가 들어가면 400)
curl -i -X POST "http://localhost:3000/prompt-updates/$PU_ID/review" \
  -H 'Content-Type: application/json' \
  -d '{"action":"approve","comment":"leak sk-proj-1234567890abcdefghijklmnopqrstuv"}'

# 3) 승인 → 적용
curl -s -X POST "http://localhost:3000/prompt-updates/$PU_ID/review" \
  -H 'Content-Type: application/json' \
  -d '{"action":"approve","reviewer":"local-test"}'

curl -s -X POST "http://localhost:3000/prompt-updates/$PU_ID/apply" \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### 3) Postgres 모드(데이터 유지 확인)

```bash
cd phase3
cp .env.example .env
# .env에서 DATABASE_URL 설정

python3 -m prism.storage.migrate
npm run seed
npm run dev
```

- 서버를 재시작해도 Case/Timeline/Prompt updates가 유지되는지 확인합니다.

## Python 유틸리티 (MVP)

- 레댁션 실행(디폴트 정책 + 리포트): `python3 -m prism.phase3.redaction_pipeline --report < input.json > redacted.json`
- GitHub 컨텍스트 번들 생성: `GITHUB_REPO=owner/repo GITHUB_TYPE=pull_request GITHUB_NUMBER=42 python3 -m prism.phase3.github_context_builder --out /tmp/context-bundle.json`
- 교훈 임베딩 검색(Top-K): `DATABASE_URL=... PRISM_EMBEDDING_MODEL=... python3 -m prism.phase3.embeddings_and_search search-lessons --role coder --query "..." --k 5`

## 회고 법정 실행(오케스트레이터)

법정 공방(prosecutor/defense/jury/judge)은 `src/prism/phase3/court_orchestrator.py`에 **라이브러리 형태**로 제공됩니다. 실제 LLM 호출은 `AgentRunner` 프로토콜 구현체로 연결하며, 테스트의 `tests/test_court_orchestrator.py`의 `FakeAgentRunner`가 최소 인터페이스 예시입니다.

## 레댁션(민감정보) 정책

- 기본 정책: `redaction-policy.default.json`
- 민감정보 정의서: `sensitive-info-spec.md`
- 원칙: **시크릿/PII는 입력 단계에서 마스킹 → 저장/공유는 마스킹된 데이터만**

## 개발 참고

- 주요 스펙 인덱스: `specs/00-index.md` (마스터: `retrospective-court-spec.md`)
- 공통 커맨드: `make setup`, `make test`, `make lint`, `make fmt`
