# Phase 2 진행 요약 (Agents + LLM)

브랜치: `phase2-agents-scaffold`

## 1) 레포/문서 정리

- 작업 가이드/설계 문서를 `phase2/`로 이동해 충돌을 줄였습니다.
  - `phase2/AGENTS.md`
  - `phase2/DEVREL_AGENT_IMPLEMENTATION.md`
- `phase2/`에 Phase2 작업 노트 및 Vector DB 결정 기록을 추가했습니다.
  - `phase2/DEVREL_AGENT_PHASE2.md`
  - `phase2/VECTOR_DB.md` (Chroma → **Postgres + pgvector** 전제)

## 2) Phase2 코드(스캐폴드) 추가

- Phase2에서 먼저 구현/검증할 작업공간을 만들었습니다.
  - `phase2/prism-devrel/src/devrel/agents/`
- Agents 출력 계약을 설계 문서의 스키마 형태로 맞추고(Structured Output-friendly),
  규칙 기반(로컬) 구현과 LLM 기반 구현 경로를 함께 두었습니다.

주요 파일:

- 스키마/타입: `phase2/prism-devrel/src/devrel/agents/types.py`
- Assignment: `phase2/prism-devrel/src/devrel/agents/assignment.py`
- Response: `phase2/prism-devrel/src/devrel/agents/response.py`
- Docs gap: `phase2/prism-devrel/src/devrel/agents/docs.py`
- Promotion: `phase2/prism-devrel/src/devrel/agents/promotion.py`

## 3) 테스트/Fixture 기반 검증

- `pytest` 스캐폴드 추가:
  - `phase2/prism-devrel/pyproject.toml`
  - `phase2/prism-devrel/tests/`
- GitHub API 응답 형태를 흉내낸 mock fixture 추가:
  - `phase2/prism-devrel/tests/fixtures/github/`
- Fixture → 내부 타입 변환 helper 추가:
  - `phase2/prism-devrel/tests/helpers/github_fixtures.py`
- 터미널에서 결과를 직접 확인하는 runner 추가:
  - `phase2/prism-devrel/scripts/run_fixtures.py`

## 4) LLM 연동(작업별 모델 라우팅)

- 작업별 모델 선택(경제적 라우팅)을 위한 selector 추가:
  - `phase2/prism-devrel/src/devrel/llm/model_selector.py`
  - 환경변수(예시): `OPENAI_MODEL_ISSUE_TRIAGE`, `OPENAI_MODEL_ASSIGNMENT`, `OPENAI_MODEL_RESPONSE`, `OPENAI_MODEL_DOCS`, `OPENAI_MODEL_PROMOTION`, `OPENAI_MODEL_JUDGE`
- Responses API 기반 LLM wrapper 추가:
  - `phase2/prism-devrel/src/devrel/llm/client.py`
- Agents에 LLM 경로(Structured Output) 추가:
  - `analyze_issue_llm`, `recommend_assignee_llm`
  - `draft_response_llm`
  - `detect_doc_gaps_llm`
  - `evaluate_promotion_llm`

## 5) .env 로딩/시크릿 관리

- `.env` 파일은 Git에 커밋되면 안 되므로 `.gitignore`에 포함되어 있습니다.
- `.env`를 자동으로 로드해 테스트/스크립트에서 키를 사용할 수 있게 했습니다.
  - pytest: `phase2/prism-devrel/tests/conftest.py`
  - runner: `phase2/prism-devrel/scripts/run_fixtures.py`
- 예시 파일:
  - `phase2/prism-devrel/.env.example`

중요: 채팅/문서/코드에 키가 노출되면 **즉시 revoke 후 재발급**해야 합니다.

## 6) 실행 방법

### (A) 로컬 규칙 기반 + fixture 출력 보기

```bash
cd phase2/prism-devrel
python scripts/run_fixtures.py
```

### (B) 실제 LLM 호출로 fixture 실행(과금/시간 발생)

`.env`에 `OPENAI_API_KEY` 및 작업별 모델을 설정한 뒤:

```bash
cd phase2/prism-devrel
USE_LLM=1 python scripts/run_fixtures.py
```

### (C) pytest

```bash
cd phase2/prism-devrel
python -m pytest -q
```

- `OPENAI_API_KEY`가 있으면 live LLM 테스트(`llm_live`, `llm_judge`)도 실행됩니다.
- 마커 정의: `phase2/prism-devrel/pyproject.toml`

## 7) 현재 상태 / 남은 작업

- 현재 브랜치에는 여러 커밋으로 Phase2 스캐폴드/테스트/LLM 연동이 올라가 있습니다.
- 로컬 워킹트리에는 아직 푸시되지 않은 보강 변경이 남아있을 수 있습니다:
  - `phase2/prism-devrel/src/devrel/llm/client.py` (일부 모델에서 JSON 출력/토큰 제한 이슈 대응)
  - `phase2/prism-devrel/src/devrel/agents/response.py`, `promotion.py`, `types.py`
  - `phase2/prism-devrel/tests/test_agents_llm_live.py`

다음 단계(협업 전제):

- 다른 팀원이 구현 중인 GitHub API 수집 레이어와 Phase2 Agents 입력/출력 연결
- pgvector 기반 검색/유사도 결과를 Agents 입력으로 주입하는 인터페이스 확정
- Phase3에서 `prism-devrel` 루트 프로젝트로 병합 + CLI/engine 연결

