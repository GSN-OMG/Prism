# 회고 법정 모듈 스펙 (v0.8)

목표: 인간/AI의 활동 기록(컨텍스트)을 “사건(Case)”으로 재구성하고, 멀티 에이전트 회고(판사/검사/변호사/배심원)를 통해 **역할(Role)별 교훈(Lesson)** 을 도출·선별하여 PostgreSQL에 축적한다. 축적된 교훈은 검색/추천에 활용되며, 필요 시 **역할별 기본 프롬프트(Base Prompt)** 업데이트(진화)를 트리거한다.

## 1) 핵심 개념

- **사건(Case)**: 회고의 최소 단위. 하나의 작업/세션/이슈/대화 묶음.
- **사건 결과(Result)**: 사건이 어떤 결과(성공/실패/부분 성공)로 끝났는지에 대한 요약/지표/에러 등.
- **컨텍스트(Context)**: 사건의 입력 데이터. 사람/에이전트 로그, 메시지, 도구 호출, 결과물 링크 등.
- **사건 피드백(Feedback)**: 사건 이후 수집된 평가/코멘트/개선 요구(사용자, 시스템 관측치 포함).
- **역할(Role)**: 교훈이 적용되는 대상 에이전트의 역할. 작업 에이전트(planner/coder/reviewer 등)뿐 아니라 **court 역할(판사/검사/변호사/배심원)도 포함**한다.
- **교훈(Lesson)**: 재사용 가능한 규칙/휴리스틱/절차. (Do/Don’t, 조건/예외, 근거 포함)
- **프롬프트 개선 권고안(Prompt Recommendation)**: 사건에 연루된 에이전트들의 기본 프롬프트를 어떻게 개선할지에 대한 제안(적용은 휴먼 승인).
- **판결(Judgement)**: 여러 후보 교훈 중 DB에 저장할 항목을 최종 선택하는 결정.
- **프롬프트 레지스트리(Prompt Registry)**: 역할별 기본 프롬프트의 버전/적용 상태를 관리.

## 1.1) 결정 사항 (현재)

- **사건 경계**: 입력으로 들어오는 모든 컨텍스트 번들(`ContextBundle`)을 사건으로 취급한다(“모든 것을 사건으로”).  
- **역할 네이밍**: 역할(`role`)은 enum이 아닌 **자유 입력 문자열**을 기본으로 한다(범용성 우선).
- **프롬프트 업데이트 운영**: 기본은 **제안만 저장**하고, 적용은 **휴먼 인 더 루프(승인 후 적용)** 로 한다.
- **교훈 중복 처리**: 유사 교훈은 **병합 또는 승계(supersede)** 를 고려한다(최종은 Judge가 결정).
- **민감정보 처리**: 정의서를 별도로 둔다. 초기에는 디폴트 정책(JSON)을 제공하고 사용자가 업데이트 가능하도록 한다. (`phase3/sensitive-info-spec.md`)
- **민감정보 정책 업데이트(MVP)**: 정책은 **파일 기반(JSON)** 으로 시작하고, 변경 사항은 **재시작 시 반영**한다(DB 즉시 갱신/핫리로드는 추후).
- **원문 저장(MVP)**: DB에는 **마스킹된 원문만 저장**한다. 마스킹 전 원문은 저장하지 않는다.
- **리뷰 수준(HITL)**: 인간 리뷰/승인은 **판사의 최종 프롬프트 권고안만** 대상으로 한다(검사/변호사/배심원 출력은 열람 전용).

## 2) 시스템 입력/출력

### 입력
- `ContextBundle` (권장 스키마: `phase3/context-bundle.schema.json`)
  - 사건에 연루된 **에이전트 정보**(id/role/현재 프롬프트 등)
  - **사건 결과(Result)** (성공/실패/지표/에러 요약 등)
  - 사건의 **컨텍스트(Context)** 이벤트 목록(대화/툴콜/코드변경/에러로그/결과 등)
  - **사건 피드백(Feedback)** (사용자/시스템 관측치 포함)

### 출력
- 1차 출력(외부로 제공되는 결과물)
  - 사건에 연루된 에이전트들에 대한 **프롬프트 개선 권고안**(제안만 저장, 휴먼 승인 후 적용)
- 2차 출력(내부 축적/자가진화)
  - DB에 저장되는 레코드(회고 법정의 자기 진화는 PostgreSQL 기반으로 유지)
    - 사건 요약/핵심 쟁점
    - 역할/대상별 교훈(텍스트 + 구조화 메타 + 임베딩)
    - 판결 기록(왜 저장/보류했는지)
	    - 프롬프트 업데이트 제안 및 적용 이력(HITL)

## 2.1) GitHub 사건 매핑 (Issue/PR, DevRel Subagents)

이 모듈이 주로 다루는 사건은 **GitHub Issue/PR에서 상주하는 DevRel 직무 관련 subagent들의 활동 이력**이다. 따라서 `ContextBundle`은 “Issue 1건” 또는 “PR 1건”을 1개의 사건으로 구성하는 것을 권장한다.

### Case 경계(권장)

- **Issue Case**: `owner/repo#issue_number` 1건 = 1 case
- **PR Case**: `owner/repo#pr_number` 1건 = 1 case
- 이벤트가 긴 경우(장기 이슈/대형 PR)는 “기간” 또는 “마일스톤” 기준으로 여러 `ContextBundle`로 분할할 수 있다(단, 사건 식별자는 동일하게 유지하거나 `parent_case_id` 같은 확장 메타를 둔다).

### 권장 메타 필드 (source/metadata)

- `source.system`: `github`
- `source.repo`: `owner/repo`
- `metadata.github` (권장)
  - `type`: `issue|pull_request`
  - `number`: issue/pr 번호
  - `url`: 웹 URL
  - `state`: `open|closed|merged`(PR의 경우)
  - `labels`: 라벨 목록
  - `assignees`: 할당자
  - `author`: 작성자(로그인)
  - (PR) `base_branch`, `head_branch`, `head_sha`
  - (선택) `milestone`, `project`, `linked_issues`

### Agents(DevRel Subagents) 기록 방식

- `agents[]`에 “사건에 연루된” subagent를 모두 나열한다.
  - 예: `devrel-triage`, `devrel-reproducer`, `devrel-pr-reviewer`, `devrel-docs-writer`, `devrel-community-manager`
- 각 항목은 최소 `id`를 포함한다. 가능하면 다음을 포함:
  - `role`(자유 입력), `prompt.content`(현재 프롬프트 기준선), `meta`(모델/버전/설정)

### Result(사건 결과) 추천 필드/지표

- `result.status`: `success|failure|partial` (운영 목적에 맞게 자유 확장)
- `result.summary`: 사건 결과 한 줄 요약
- `result.metrics` (권장, DevRel 운영 지표)
  - `time_to_first_response_sec`
  - `time_to_close_sec` / `time_to_merge_sec`
  - `num_comments`, `num_review_comments`
  - `num_review_roundtrips` (changes requested 횟수 등)
  - `num_ci_failures` / `num_ci_retries`
  - `num_force_pushes` / `num_syncs`
  - (선택) `user_sentiment`(휴먼 입력 기반이면 OK)
- `result.artifacts`: 링크/스냅샷(예: 로그 URL, 빌드 링크, 릴리즈 노트)

### Feedback(사건 피드백) 추천

- `feedback.summary`: 사건 회고용 요약(사용자/내부 리뷰어 관점)
- `feedback.items[]`: 구조화 객체 권장(예: `{ "author": "...", "type": "review", "content": "...", "severity": "low|med|high" }`)

### Events(컨텍스트 타임라인) 권장 규칙

- 정렬: `events[].ts` 우선, 없으면 `events[].seq`로 순서를 보장
- `actor_type` 권장 매핑
  - GitHub 사용자/리뷰어: `human`
  - DevRel subagent: `ai`
  - GitHub/CI/자동화: `system`
  - GitHub API 호출/임베딩/DB 작업 등: `tool`
- `event_type` 네이밍 권장(필터링/분석/GUI에 유리)
  - GitHub 원천 이벤트: `github.issue.*`, `github.pull_request.*`, `github.review.*`, `github.ci.*`
  - 에이전트 내부 이벤트: `agent.plan`, `agent.message`, `agent.decision`, `agent.action`
  - 운영/관측 이벤트: `tool_call`, `tool_result`, `model_call`, `model_result`, `error`, `artifact`
- `meta`에 GitHub 식별자/링크를 넣어 “원문은 짧게, 참조는 풍부하게”
  - 예: `meta.github.comment_id`, `meta.github.url`, `meta.github.diff_hunk`, `meta.github.review_state`
- `usage`에는 운영 정보를 넣는다(토큰/비용/지연/재시도/레이트리밋 등).

### 이벤트 타입 예시 (GitHub)

- Issue
  - `github.issue.opened`, `github.issue.labeled`, `github.issue.assigned`, `github.issue.comment.created`, `github.issue.closed`, `github.issue.reopened`
- Pull Request
  - `github.pull_request.opened`, `github.pull_request.synchronized`, `github.pull_request.ready_for_review`, `github.pull_request.review.submitted`, `github.pull_request.review_comment.created`, `github.pull_request.merged`, `github.pull_request.closed`
- CI/Automation
  - `github.ci.check_run.completed`, `github.ci.workflow_run.completed`

## 2.2) GitHub → ContextBundle 예시(간단)

```json
{
  "version": "0.1",
  "source": { "system": "github", "repo": "owner/repo", "tags": ["pull_request"] },
  "metadata": { "github": { "type": "pull_request", "number": 42, "url": "...", "state": "merged" } },
  "agents": [{ "id": "devrel-pr-reviewer-1", "role": "devrel-pr-reviewer" }],
  "result": { "status": "success", "summary": "PR merged", "metrics": { "time_to_merge_sec": 86400 } },
  "feedback": { "summary": "Review was helpful", "items": [] },
  "events": [
    { "id": "e1", "ts": "2026-01-20T04:00:00Z", "actor_type": "human", "actor_id": "contributor", "event_type": "github.pull_request.opened", "content": "Opened PR #42", "meta": { "github": { "url": "..." } } },
    { "id": "e2", "ts": "2026-01-20T04:10:00Z", "actor_type": "ai", "actor_id": "devrel-pr-reviewer-1", "role": "devrel-pr-reviewer", "event_type": "agent.plan", "content": "Plan review steps", "usage": { "model": "gpt-4.1", "latency_ms": 1200, "input_tokens": 1200, "output_tokens": 250 } },
    { "id": "e3", "ts": "2026-01-20T04:12:00Z", "actor_type": "tool", "actor_id": "github_api", "event_type": "tool_call", "content": "GET PR files", "meta": { "endpoint": "GET /repos/{owner}/{repo}/pulls/{pull_number}/files" }, "usage": { "rate_limit_remaining": 4980 } }
  ]
}
```

## 3) 멀티 에이전트 워크플로우 (Court)

### 단계 개요
1. **케이스 생성/정규화**
   - 컨텍스트를 이벤트(증거) 단위로 정규화하고 `case_id` 발급
   - 민감정보(PII/API 키) 마스킹 정책 적용(디폴트: `phase3/redaction-policy.default.json`)
2. **검사(Prosecutor)**: 비판 중심 분석
   - “무엇이 잘못됐는가 / 재발 방지 규칙은 무엇인가”에 집중
   - 대상: 사건에 연루된 **에이전트뿐 아니라 사용자(User)·시스템(System)의 기여/결함**도 포함
3. **변호사(Defense)**: 칭찬 중심 분석
   - “무엇이 잘됐는가 / 유지·확대할 원칙은 무엇인가”에 집중
   - 대상: 에이전트/사용자/시스템 모두 가능
4. **배심원(Jury)**: 중립적 관찰/대안 제시
   - 쟁점 정리, 상충되는 관점, 트레이드오프, 누락된 정보 지적
5. **판사(Judge)**: 최종 판결
   - (a) DB에 저장할 교훈 후보 선택/정제
   - (b) 사건에 연루된 에이전트들의 프롬프트 개선 권고안을 생성(적용은 휴먼 승인 이후)
   - (c) (선택) 사용자/시스템 개선점(프로세스/가이드/정책)도 별도 항목으로 기록
6. **저장/색인**
   - 교훈 텍스트 임베딩 생성 후 DB에 저장
   - 유사 교훈 중복/충돌 검사(선택)

### 오케스트레이션(권장: OpenAI Agents SDK)

- Court 역할(판사/검사/변호사/배심원)은 각각 **독립 Agent** 로 정의한다.
- 실행은 `Prosecutor/Defense/Jury → Judge`의 고정 시퀀스를 기본으로 하되, `Prosecutor`, `Defense`, `Jury`는 의존성이 낮으므로 **병렬 실행**도 고려한다.
- 모든 에이전트 출력은 **구조화(JSON)** 를 우선으로 하여, 후처리/저장/검증이 가능해야 한다.
- 공용 툴(예시):
  - `get_case(case_id)`: 케이스 메타/요약 조회
  - `list_case_events(case_id)`: 증거 이벤트 조회(마스킹된 데이터)
  - `search_lessons(role, query)`: 유사 교훈 검색(중복/충돌 검사용)
  - `propose_prompt_update(role, proposal, reason)`: 프롬프트 업데이트 제안 기록

### GUI (HITL + 감사/운영 관측)

목표: 각 공방(run) 결과를 사람이 빠르게 리뷰하고, **판사의 최종 권고안만 승인/반려**할 수 있게 한다. 또한 court 및 사건 진행 중 생성된 **운영 정보(툴콜/토큰/비용/에러/지연)** 를 시계열로 확인한다.

- 필수 화면(MVP)
  - Case 목록: `cases` + 최신 `court_runs` 상태
  - Case 상세:
    - 타임라인(시계열): `case_events`를 `ts`(없으면 `seq`)로 정렬, 필터(actor/role/event_type)
    - 공방 결과 탭: Prosecutor/Defense/Jury/Judge의 구조화 출력(JSON)
    - Judge 권고안 리뷰: `prompt_updates(status=proposed)` 리스트 + diff/전체 프롬프트 보기
    - 승인/반려(HITL): `prompt_updates.status`를 `approved` 또는 `rejected`로 변경 + 코멘트 저장(선택)
- 운영 정보 표시(타임라인 이벤트 예시)
  - `tool_call` / `tool_result` (도구명, 인자/결과 요약, 실패 시 에러)
  - `model_call` / `model_result` (모델명, latency, token usage, cost)
  - `error` (스택/원인 요약, 재시도 여부)
  - `artifact` (링크/파일 경로/출력 요약)
  - 모든 텍스트/아티팩트는 **redacted 상태만** UI에 노출

### 각 에이전트 출력 형식(권장: JSON)
모든 에이전트는 **근거(evidence)** 를 컨텍스트 이벤트 ID로 참조해야 하며, 사건에 없는 내용을 “추정”으로 표기한다.

- Prosecutor: `criticisms[]`, `candidate_lessons[]`
- Defense: `praises[]`, `candidate_lessons[]`
- Jury: `observations[]`, `risks[]`, `missing_info[]`, `candidate_lessons[]`
- Judge:
  - `selected_lessons[]` (저장 확정)
  - `deferred_lessons[]` (보류 + 이유)
  - (선택) `prompt_update_proposals[]`
  - (선택) `user_improvement_suggestions[]`, `system_improvement_suggestions[]`

## 4) 저장소/DB 설계 (PostgreSQL)

### 확장
- `pgvector` 사용(권장): 교훈 임베딩 벡터 저장 및 ANN 검색.

### 테이블 초안
- `cases`
  - `id`, `created_at`, `source`, `summary`, `status`
  - (선택) `redaction_policy_id`, `redaction_policy_version`
- `case_events`
  - `id`, `case_id`, `ts`, `seq`(bigint, optional), `ingested_at`
  - `actor_type`(human/ai/tool/system), `actor_id`, `role`(optional)
  - `event_type`, `content`(redacted), `meta`(jsonb)
  - (선택) `court_run_id` (공방 실행과 연결)
- `court_runs`
  - `id`, `case_id`, `model`, `started_at`, `ended_at`, `status`, `artifacts`(jsonb: redacted 응답/토큰/비용 등)
- `lessons`
  - `id`, `case_id`, `role`, `polarity`(do/dont), `title`, `content`, `rationale`, `confidence`
  - `tags`(text[]), `evidence_event_ids`(uuid[] 또는 bigint[])
  - `embedding`(vector), `embedding_model`, `embedding_dim`
  - `created_at`, `supersedes_lesson_id`(선택)
- `judgements`
  - `id`, `case_id`, `court_run_id`, `decision`(jsonb: selected/deferred + 이유), `created_at`
- `role_prompts`
  - `id`, `role`, `version`, `prompt`, `created_at`, `is_active`
- `prompt_updates`
  - `id`, `role`, `from_version`, `proposal`(diff 또는 full prompt), `reason`
  - `status`(proposed/approved/applied/rejected), `created_at`, `approved_at`, `applied_at`
  - (선택) `approved_by`(human identifier)
  - (선택) `agent_id`(사건 입력의 에이전트 식별자)
  - (선택) `review_comment`

- `redaction_policies`
  - `id`, `version`, `policy`(jsonb), `created_at`, `is_active`

- (선택) `improvements`
  - `id`, `case_id`, `target_type`(user/system), `title`, `content`, `rationale`, `evidence_event_ids`, `created_at`

### 유사 교훈 병합/승계(권장 운영)

- 신규 교훈 저장 전, 같은 `role` 내에서 임베딩 유사 검색(Top-K)으로 **중복 후보**를 찾는다.
- Judge는 다음 중 하나를 선택한다.
  - **누적 저장**: 새 교훈을 그대로 저장(기존과 공존)
  - **승계(supersede)**: 새 교훈이 기존 교훈을 대체한다고 판단 → `supersedes_lesson_id`로 연결
  - **병합(merge)**: 기존 교훈들의 내용을 통합한 “정리본”을 새 교훈으로 저장하고, 대표 교훈으로 승계 연결(또는 향후 `lesson_links` 같은 링크 테이블로 확장)

### 검색 쿼리(예)
- 역할별 유사 교훈 Top-K: `WHERE role = $role ORDER BY embedding <-> $query_embedding LIMIT $k`

## 5) 프롬프트 업데이트 정책 (진화)

### 기본 원칙
- “교훈 저장”과 “프롬프트 변경”은 분리한다. 기본은 **제안만 저장**하고, 적용은 **휴먼 승인 이후**에만 수행한다.
- 프롬프트는 항상 **버전 관리 + 롤백 가능**해야 한다.

### 적용 트리거(예시)
- 동일 역할에서 유사 교훈이 반복적으로 축적됨
- 특정 실패 유형(예: 보안/데이터손실)이 높은 심각도로 발생
- Judge가 높은 confidence로 업데이트 필요 판정

## 6) 임베딩 전략

- 후보: **model2vec 다국어 모델**
- 저장 시 필드:
  - `embedding_model`: 모델 식별자(예: repo/name@version)
  - `embedding_dim`: 차원
- 주의:
  - pgvector 인덱싱을 위해 차원/모델은 운영에서 가급적 고정
  - 동일 교훈이라도 모델 변경 시 재임베딩 작업 필요(마이그레이션 계획 포함)

## 7) MVP 범위(제안)

1. `ContextBundle` → `case_events` 적재 + `cases` 생성
2. Court 4에이전트 1회 실행 → Judge가 프롬프트 개선 권고안(`prompt_update_proposals`) 산출
3. 권고안은 `prompt_updates`에 “proposed”로 저장(HITL 승인/적용은 수동)
4. (병행) 교훈 임베딩 생성 → `lessons` 저장(중복/승계 고려)
5. `search_lessons(role, query)`로 유사 교훈 Top-K 조회
6. (선택) 사용자/시스템 개선점은 `improvements`로 저장

## 8) 오픈 질문(결정 필요)

1. **병합/승계 기준**: 임베딩 유사도 임계값, “동일 내용” 판정 기준, 충돌 시 우선순위(최신/신뢰도/심각도) 정의.
2. **프롬프트 권고안 포맷**: `proposal`을 diff로 저장할지, 완전한 full prompt로 저장할지(또는 둘 다).
3. **입력의 프롬프트 기준선**: 사건 입력(`ContextBundle.agents[].prompt`)에 “현재 프롬프트”를 포함할지, 아니면 DB의 `role_prompts`에서 조회할지.
4. **사용자/시스템 개선점 저장 방식**: `improvements` 테이블로 분리 vs `lessons`에 `role=user|system`으로 저장(운영/검색 관점에서 결정).
