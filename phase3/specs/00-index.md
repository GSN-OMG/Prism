# Phase 3 분할 스펙 인덱스 (Parallel Dev)

목표: `phase3/retrospective-court-spec.md`(통합 스펙)의 기능을 **병렬 개발 가능**하도록 독립 모듈로 쪼갠다. 각 모듈은 입력/출력(계약)과 의존성을 명확히 한다.

## 모듈 목록

1. **GitHub 컨텍스트 빌더** → `01-github-context-builder.md`  
   - GitHub Issue/PR 데이터를 수집해 `ContextBundle`로 정규화.
2. **민감정보 마스킹(레댁션)** → `02-redaction-pipeline.md`  
   - JSON 정책 기반으로 모든 텍스트/메타를 마스킹(“masked-only storage” 강제).
3. **DB/스토리지(POSTGRES)** → `03-postgres-storage.md`  
   - `cases/case_events/court_runs/lessons/prompt_updates/...` 스키마, 인덱스, 저장 API.
4. **Court 오케스트레이터(Agents SDK)** → `04-court-orchestrator.md`  
   - Prosecutor/Defense/Jury → Judge 실행 + 결과 저장 + 타임라인 이벤트/운영정보 기록.
5. **임베딩/유사도/검색** → `05-embeddings-and-search.md`  
   - model2vec 임베딩 생성, pgvector 저장, 유사 교훈 검색/중복 후보 탐지.
6. **프롬프트 레지스트리 + HITL 승인** → `06-prompt-registry-hitl.md`  
   - Judge 권고안을 `proposed`로 저장, 인간 승인 후 적용(버전 관리/롤백).
7. **GUI(리뷰 + 타임라인)** → `07-gui-review-timeline.md`  
   - 판사 최종 권고안만 승인/반려 + 시계열 타임라인(운영정보 포함).
8. **시크릿/설정(운영 가이드)** → `08-secrets-and-config.md`  
   - API Key 등 시크릿을 코드/DB/로그에 남기지 않는 운영 방법.

## 의존성(권장 구현 순서)

- (A) `02-redaction-pipeline` + `03-postgres-storage`는 가장 먼저(전 모듈이 “masked-only”와 저장 계약을 공유).
- (B) `01-github-context-builder`는 A에 의존(수집 후 저장/마스킹).
- (C) `04-court-orchestrator`는 A에 의존, (옵션) `05-embeddings-and-search`와 결합.
- (D) `06-prompt-registry-hitl`은 `04` 결과를 저장/승인/적용.
- (E) `07-gui-review-timeline`은 `03/04/06`의 읽기/쓰기 API에 의존.

## 공통 계약(모든 모듈 준수)

- DB에 저장되는 텍스트/아티팩트는 **반드시 redacted 상태**여야 한다.
- 모든 에이전트 출력은 **구조화(JSON)** 를 우선으로 한다.
- 타임라인은 `case_events`를 기준으로 하며, 운영정보(`usage`, `error`, `tool_call` 등)도 이벤트로 기록한다.

