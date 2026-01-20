# Court 오케스트레이터 스펙 (OpenAI Agents SDK)

목표: Prosecutor/Defense/Jury/Judge 멀티 에이전트 공방을 실행하고, 결과를 저장하며, Judge의 **프롬프트 개선 권고안**을 생성한다.

## 입력/출력

- 입력: `case_id` (DB에서 `cases/case_events` 로드)
- 출력:
  - `court_runs` + `case_events`에 실행 트레이스(운영정보 포함)
  - `judgements`, `lessons`, `prompt_updates(status=proposed)`
  - (선택) `improvements` (user/system 개선점)

## 실행 순서

1. `Prosecutor`, `Defense`, `Jury` 병렬 실행(가능하면)  
2. `Judge` 실행(위 3개 출력 + 사건 컨텍스트/결과/피드백을 입력으로)

## 에이전트 역할 정의(요약)

- Prosecutor: 에이전트/유저/시스템의 문제점을 비판 → 후보 교훈
- Defense: 잘한 점 칭찬 → 후보 교훈
- Jury: 중립 관찰 + 누락/리스크 지적 → 후보 교훈
- Judge:
  - 교훈 저장 여부 결정(`selected_lessons`)
  - **프롬프트 개선 권고안** 생성(`prompt_update_proposals`)
  - (선택) `user_improvement_suggestions`, `system_improvement_suggestions`

## 구조화 출력(JSON) 강제

- 모든 에이전트는 JSON 스키마에 맞는 결과만 반환하도록(Agents SDK structured output 사용 권장)
- 모든 항목은 `evidence_event_ids[]`로 근거를 연결한다.

## 툴/데이터 접근

- LLM에 제공되는 컨텍스트는 반드시 redacted 데이터여야 한다.
- 공용 툴(예시):
  - `get_case(case_id)`
  - `list_case_events(case_id)`
  - `search_lessons(role, query)` (중복 후보 탐지)

## 타임라인/운영정보 기록

- `case_events`에 다음을 이벤트로 append:
  - `model_call/model_result` (tokens/cost/latency)
  - `tool_call/tool_result` (요약/에러)
  - `error` (실패/재시도 기록)
  - `artifact` (JSON 결과 스냅샷 링크/요약)

## 실패 처리(권장)

- Prosecutor/Defense/Jury 중 일부 실패해도 Judge는 가능한 범위에서 진행(상태를 artifacts에 기록)
- 재시도/타임아웃 정책은 `meta`/`usage`로 기록

## 완료 조건(MVP)

- case_id로 Court 1회 실행 가능
- Judge가 `prompt_updates(status=proposed)`를 생성/저장
- 모든 이벤트/아티팩트는 redacted 상태로만 저장

