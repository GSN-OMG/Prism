# GUI 스펙 (판사 권고안 리뷰 + 타임라인)

목표: 인간이 사건/공방을 시각적으로 리뷰하고, **Judge 최종 권고안만 승인/반려**한다. 또한 운영정보(토큰/비용/툴콜/에러)를 시계열로 확인한다.

## 화면(MVP)

1. Case 목록
   - `cases` + 최신 `court_runs.status`
2. Case 상세
   - 타임라인: `case_events`를 `ts`(없으면 `seq`) 기준 정렬
   - 필터: `actor_type`, `actor_id`, `role`, `event_type`, `stage`
   - 공방 결과 탭: Prosecutor/Defense/Jury/Judge JSON 보기
   - 권고안 리뷰: `prompt_updates(status=proposed)` 목록
     - diff 뷰(가능하면) + full prompt 보기
     - Approve / Reject + 코멘트

## API(논리)

- `GET /cases`
- `GET /cases/:id`
- `GET /cases/:id/events?filters...`
- `GET /cases/:id/court-runs`
- `GET /prompt-updates?case_id=&status=proposed`
- `POST /prompt-updates/:id/review` (approve/reject + comment)

## 보안/마스킹

- UI는 redacted 데이터만 표시한다(서버가 보장).
- 운영정보(`usage`)도 민감정보(엔드포인트/에러 메시지 등) 마스킹 적용.

## 완료 조건(MVP)

- Case 상세에서 타임라인 + Judge 권고안 승인/반려 가능

