# GitHub 컨텍스트 빌더 스펙 (Issue/PR → ContextBundle)

목표: GitHub Issue/PR에서 발생한 상호작용과 DevRel subagent 활동 이력을 수집/정규화하여 `ContextBundle`로 만든다.

## 범위

- 입력: `owner/repo`, `type(issue|pull_request)`, `number`, (선택) 수집 기간/페이지 제한
- 출력: `ContextBundle` JSON (`context-bundle.schema.json` 준수)
- (선택) 바로 DB에 적재: `cases`, `case_events`

## 비범위(초기)

- GitHub 전체 이벤트 스트리밍(웹훅 기반 상시 수집)은 추후
- 고급 NLP(감성 분석 자동화 등)는 추후

## 입력/출력 계약

### 입력
- GitHub API 접근 정보(토큰 등)는 **환경변수**로만 주입하고, 로그/DB에 남기지 않는다.
- 수집 파라미터 예:
  - `GITHUB_REPO=owner/repo`
  - `GITHUB_TYPE=pull_request`
  - `GITHUB_NUMBER=42`

### 출력: ContextBundle 필드 구성(권장)
- `source.system=github`, `source.repo=owner/repo`
- `metadata.github`: `{ type, number, url, state, labels, assignees, author, ... }`
- `agents[]`: DevRel subagent들(사건 연루자) 나열
  - subagent 식별은 “GitHub 계정/봇 이름 매핑” 또는 “사전 등록된 agent_id 목록”으로 해결
- `result`: `status/summary/metrics/artifacts`
- `feedback`: `summary/items[]` (리뷰 코멘트/회고 코멘트)
- `events[]`: 타임라인 이벤트(정렬은 `ts` 우선, 없으면 `seq`)

## 이벤트 수집 대상(권장)

- Issue: opened/closed/reopened, labeled, assigned, comments
- PR: opened/closed/merged, commits, files changed(링크만), review submitted, review comments, ready_for_review, synchronize
- CI/Automation: check runs, workflow runs(요약)

## event_type 컨벤션(권장)

- GitHub 원천: `github.issue.*`, `github.pull_request.*`, `github.review.*`, `github.ci.*`
- 에이전트 내부: `agent.plan`, `agent.message`, `agent.decision`, `agent.action`
- 운영/관측: `tool_call`, `tool_result`, `model_call`, `model_result`, `error`, `artifact`

## 운영 지표(result.metrics) (권장)

- `time_to_first_response_sec`
- `time_to_close_sec` / `time_to_merge_sec`
- `num_comments`, `num_review_comments`
- `num_review_roundtrips`
- `num_ci_failures`, `num_ci_retries`
- `rate_limit_events` (선택)

## 저장 전략(선택)

### 옵션 A: ContextBundle만 생성
- downstream(저장/오케스트레이터)이 `ContextBundle`을 받아 처리

### 옵션 B: DB 적재까지 수행
- `cases` 생성 후, `events[]`를 `case_events`로 upsert/append
- 이때 “masked-only storage” 정책 때문에, **DB 적재 전에 반드시 레댁션 모듈**을 호출한다.

## 에러/재시도/레이트리밋

- GitHub API 실패는 `case_events`에 `error`로 기록(원문 에러에 시크릿 포함 시 마스킹)
- rate limit 상황은 `usage.rate_limit_remaining/reset_at` 등으로 기록

## 완료 조건(MVP)

- PR 1건을 입력하면 `ContextBundle` 생성 가능
- `events[]`에 최소: opened, comment, review, ci 결과(있다면) 이벤트가 들어감
- `result.metrics.time_to_first_response_sec`와 `time_to_merge_sec` 중 가능한 항목 계산
