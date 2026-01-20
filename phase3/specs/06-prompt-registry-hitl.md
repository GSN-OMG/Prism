# 프롬프트 레지스트리 + HITL 승인 스펙

목표: Judge가 만든 “프롬프트 개선 권고안”을 `proposed`로 저장하고, 인간이 승인/반려한 뒤에만 역할별 기본 프롬프트를 갱신한다.

## 엔티티

- `role_prompts`: 역할별 기본 프롬프트 버전/활성 상태
- `prompt_updates`: 권고안(제안) + HITL 상태(`proposed/approved/rejected/applied`)

## 워크플로우

1. Judge가 `prompt_update_proposals[]` 생성
2. 시스템은 이를 `prompt_updates(status=proposed)`로 저장
3. 인간 리뷰어가 **판사 권고안만** 승인/반려
4. 승인된 권고안만 `apply` 가능:
   - 새 `role_prompts` 버전 생성 + `is_active=true` (이전 버전 비활성화)
   - `prompt_updates.status=applied`, `applied_at` 기록

## proposal 포맷(권장)

- 최소: `role`, (선택) `agent_id`, `reason`, `evidence_event_ids`
- 프롬프트 본문은 “full prompt” 형태를 우선 권장
  - diff는 GUI에서 생성하거나, 저장 시 함께 넣어도 됨(오픈 질문)

## 완료 조건(MVP)

- proposed/approved/rejected/applied 상태 전이 구현
- role_prompts 버전 관리 및 활성 1개 보장

