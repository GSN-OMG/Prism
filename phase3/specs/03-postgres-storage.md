# PostgreSQL 스토리지 스펙

목표: 사건/이벤트/공방 실행/교훈/프롬프트 권고안/HITL 상태를 PostgreSQL에 저장한다. self-evolution의 source of truth는 PostgreSQL로 고정한다.

## 핵심 원칙

- DB에는 **redacted 데이터만** 저장한다.
- 타임라인은 `case_events`가 유일한 소스이며, 운영정보도 이벤트로 기록한다.

## 테이블(초안)

통합 스펙의 테이블을 따른다: `cases`, `case_events`, `court_runs`, `lessons`, `judgements`, `role_prompts`, `prompt_updates`, `redaction_policies`, (선택) `improvements`.

## 인덱스/쿼리(권장)

- `case_events(case_id, ts)` + `case_events(case_id, seq)` (ts 없는 경우 대비)
- `prompt_updates(status, created_at)`
- `lessons(role)` + (pgvector 인덱스는 임베딩 모듈에서 정의)

## 저장 API(논리 인터페이스)

- `create_case(source, metadata, redaction_policy_version) -> case_id`
- `append_case_events(case_id, events[])`
- `create_court_run(case_id, model, started_at) -> court_run_id`
- `finish_court_run(court_run_id, status, artifacts_redacted)`
- `store_judgement(case_id, court_run_id, decision_json)`
- `store_lessons(case_id, lessons[])`
- `store_prompt_update(case_id, agent_id?, role, from_version?, proposal, reason) -> prompt_update_id`
- `review_prompt_update(prompt_update_id, status=approved|rejected, review_comment, approved_by)`
- `apply_prompt_update(prompt_update_id) -> new_role_prompt_version`

## 완료 조건(MVP)

- 위 API를 최소 동작으로 구현(ORM/SQL 상관 없음)
- `case_events`에 `ingested_at` 자동 기록
- 마스킹 전 원문이 DB에 들어가지 않도록 테스트/가드 포함

