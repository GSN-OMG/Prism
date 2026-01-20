# openai/openai-agents-python raw_http 기반 “시스템 프롬프트 업데이트 에이전트” 기획서 (v0)

기준일: **2026-01-20 (UTC)**  
데이터 범위(예시): **ClosedAt 기준 2주**(예: 2026-01-06 ~ 2026-01-20)  
대상 레포: `openai/openai-agents-python`

## 1) 한 줄 요약

GitHub `raw_http`(Closed PR/Issue 스냅샷)에서 **레포의 실제 운영 방식/용어/규칙/반복 이슈**를 추출해, `AGENTS_SUMMARY.md`에 정리된 여러 에이전트의 **시스템 프롬프트를 “증거 기반으로” 더 정확하고 레포 친화적으로 자동 개선**하는 에이전트를 만든다.

관련 문서(수집/ETL 초안): `docs/openai-agents-python-closedAt-2w-etl-spec.md`

---

## 2) 배경/문제 정의

DevRel 에이전트(문서/예제/가이드/이슈 대응 등)는 “레포 고유의 맥락”이 없으면 다음 문제가 자주 발생한다.

- 레포의 실제 정책(리뷰 방식, 선호하는 해결 방식, 라벨 의미, 금지/권장 패턴)을 모른 채 일반론으로 답한다.
- Closed 이슈/PR에 이미 반복된 결정/FAQ를 놓쳐서 “중복 안내”를 하거나, 이미 거절된 제안을 다시 권한다.
- maintainers/리뷰어/자동화(봇)의 역할을 구분하지 못해 커뮤니케이션 톤/타겟이 어긋난다.

반대로, `raw_http`에는 “실제로 닫힌 토론/결정”이 있어 **운영의 현실(ground truth)**이 드러난다. 이 데이터를 가공해 프롬프트에 반영하면 DevRel 품질이 즉시 올라간다.

---

## 3) 목표(Goals) / 비목표(Non-goals)

### Goals
- `raw_http` → 정규화/요약 → **레포 인사이트 팩(repo insight pack)** 생성
- `AGENTS_SUMMARY.md`(에이전트 목록/현재 시스템 프롬프트) + 인사이트 팩을 입력으로
  - 에이전트별 시스템 프롬프트를 **레포 맞춤으로 업데이트**
  - 업데이트 근거(증거 링크/이슈·PR 번호)를 함께 출력
- 업데이트 결과를 검증하기 위한 **회귀용 평가 세트(프롬프트 테스트 케이스)**와 리포트 산출

### Non-goals (v0)
- raw 데이터를 “수정”하거나 누락을 메우기 위해 임의로 필드를 추정/보정하지 않는다(원본은 불변).
- 레포 코드/문서 전체를 크롤링해 지식베이스를 만드는 것은 v0 범위 밖(옵션 확장으로 정의).
- 자동으로 PR/Issue에 댓글을 다는 봇까지는 v0에 포함하지 않는다(내부 프롬프트/가이드 생성에 집중).

---

## 4) 핵심 컨셉: “증거 기반 프롬프트 리라이트”

프롬프트를 “더 길게” 만드는 것이 목표가 아니라,

1) **규칙/금지/선호**를 명시하고  
2) **업무 흐름(워크플로우)**을 구체화하며  
3) **불확실할 때의 질문(clarifying questions)**을 강제하고  
4) 무엇보다 **근거(Closed PR/Issue의 결정/패턴)**를 프롬프트에 연결한다.

출력물은 “자연어 프롬프트”와 함께 “근거 JSON”을 같이 내보내어, 사람이 검토/승인할 수 있게 한다.

---

## 5) 입력/출력(Interfaces)

### 5.1 Inputs
- `raw_http` 디렉터리
  - 예: `raw/<owner>-<repo>/closedAt_<start>_<end>_<timestamp>/raw_http/**.json`
  - REST Search + GraphQL hydration 결과(코어/댓글/리뷰/타임라인/파일 등)
- `AGENTS_SUMMARY.md` (필수, 별도 위치 가능)
  - 에이전트별: `agent_id`, `purpose`, `current_system_prompt`, (선택) `tools`, `examples`, `constraints`
- (옵션) 레포 메타 파일
  - `README.md`, `CONTRIBUTING.md`, `CODEOWNERS`, 릴리즈 노트 등(“정책 문서”로서 우선순위 높음)

### 5.2 Outputs
1. **Repo Insight Pack**
   - `out_insights/repo_insights.json`
   - `out_insights/repo_insights.md` (사람용 요약)
2. **프롬프트 업데이트 결과**
   - `out_prompts/<agent_id>.system.prompt.md`
   - `out_prompts/<agent_id>.changes.json` (변경 요약, 근거 링크, 적용된 룰)
3. **평가/리포트**
   - `out_reports/prompt_regression_report.md`
   - `out_reports/prompt_regression_cases.jsonl` (케이스: 입력 질문/기대 행동/근거)

---

## 6) 데이터 가공 설계(ETL → 인사이트)

이 레포는 “raw HTTP JSON 보존”이 우선이며, 가공은 파생 산출물로 분리한다.

### 6.1 v0에서 추가로 만들 파생 뷰(권장)

현재 `repo_user`, `repo_user_activity`만으로는 “프롬프트에 넣을 레포 규칙/패턴”을 만들기 어렵다. v0에서 최소 아래 뷰를 추가한다.

- `repo_work_item` (Issue/PR 단위)
  - 키: `repo_full_name`, `number`, `type(issue|pr)`
  - 필드: `title`, `state`, `created_at`, `closed_at`, `author_login`, `author_association`, `labels[]`, `milestone`, `is_merged`, `merged_at`, `merged_by`, `comment_count`, `review_count`
- `repo_work_item_event` (타임라인 이벤트)
  - 키: `repo_full_name`, `number`, `event_type`, `created_at`, `actor_login`
  - 라벨/할당/닫힘/재오픈/크로스레퍼런스 등
- `repo_pr_review` (리뷰 단위)
  - 키: `repo_full_name`, `pr_number`, `review_id`
  - 필드: `author_login`, `state`, `submitted_at`
- (선택) `repo_pr_file` / `repo_pr_change_summary`
  - 파일 경로 기반으로 “변경이 자주 일어나는 영역”을 집계(DevRel이 안내해야 할 hot path)

### 6.2 인사이트 추출(예시 항목)

**운영/프로세스**
- 라벨 taxonomy: `feature:*`, `bug`, `docs`, `good first issue` 등 “실제 쓰이는 라벨”과 빈도/공동 등장
- 일반적인 클로징 사유 패턴: “지원 범위 아님”, “재현 불가”, “이미 해결됨”, “PR로 해결 유도” 등
- 리뷰 패턴: 리뷰어 풀, 승인/변경요청의 비율, 평균 리뷰 지연(근사), 자주 등장하는 코멘트 키워드

**제품/기술 영역**
- 자주 등장하는 기능 영역(라벨/제목/본문/파일 경로 기반 토픽)
- 사용자들이 막히는 지점(반복되는 질문, 에러 메시지, 설정 이슈)

**커뮤니케이션 톤**
- maintainers의 응답 스타일(간결/링크 중심/재현 요청/템플릿 유도)
- “질문하기 전에 필요한 정보” 체크리스트(재현 steps, 버전, 환경 등)

> 원칙: 인사이트는 반드시 “근거 목록”(이슈/PR 번호, URL)을 함께 가진다.

---

## 7) 프롬프트 업데이트 로직(Agent Design)

### 7.1 구성 요소

1) **Insight Builder**
- 입력: `raw_http` + (옵션) 레포 메타 파일
- 출력: `repo_insights.json` (증거 포함)

2) **Prompt Refiner**
- 입력: `AGENTS_SUMMARY.md` + `repo_insights.json`
- 출력: 에이전트별 업데이트된 시스템 프롬프트 + 변경 근거

3) **Prompt Evaluator**
- 입력: 업데이트된 프롬프트 + 회귀 케이스
- 출력: 리포트(누락된 규칙, 모순, 너무 구체/너무 일반, 금지 위반 등)

### 7.2 Refiner의 출력 정책(프롬프트 템플릿 골격)

에이전트별 시스템 프롬프트는 최소 아래 섹션을 갖게 한다.

- `Mission`: 에이전트의 역할을 1~2문장으로 고정
- `Repo-Specific Context`: 인사이트 팩에서 “가장 중요한 5~15개 규칙/용어/워크플로우”만 포함
- `Operating Rules`: 사실 불명확 시 질문하기, 근거 없는 단정 금지, 링크/버전 확인 등
- `Style`: 톤(DevRel), 출력 포맷(예: 재현 steps, 코드/명령어), 한국어/영어 정책
- `Escalation`: 데이터/근거 부족 시 “어떤 정보를 요구해야 하는지” 체크리스트

### 7.3 충돌/품질 관리

- **충돌 해결 우선순위**
  1) 레포 정책 문서(옵션 입력)
  2) Closed 이슈/PR에서 반복된 결정 패턴(빈도/최근성 가중)
  3) 기타 일반 베스트 프랙티스(마지막)
- **안전장치**
  - 인사이트에 근거가 없으면 프롬프트에 “규칙”으로 넣지 말고 “가능성/추정”으로 표기하거나 제외
  - 특정 개인(maintainer)에게 과도하게 책임/권한을 부여하는 문장 금지(역할은 관찰된 데이터로만)

---

## 8) `AGENTS_SUMMARY.md` 기대 포맷(제안)

현재 파일이 없거나 포맷이 불명확한 경우를 대비해, v0에서 다음 형태를 권장한다.

- 최상단: 대상 레포, 목적, 에이전트 목록 인덱스
- 에이전트 섹션(반복):
  - `## <agent_id>`
  - `Purpose:` (한 줄)
  - `Current System Prompt:` (코드 블록)
  - `Tools:` (선택)
  - `Constraints:` (선택)
  - `Examples:` (선택)

Refiner는 위 구조를 파싱해 “시스템 프롬프트 블록”만 교체/업데이트한다.

---

## 9) 성공 지표(Success Metrics)

- 프롬프트 업데이트가 “레포 관점에서 유효한 규칙”을 포함하고 있는가?
  - 규칙/권장/금지가 **근거 링크**와 함께 제시됨
- DevRel 품질 지표(오프라인 평가)
  - 반복 질문에 대한 답변이 Closed 결정과 일치하는가?
  - 불확실할 때 질문을 먼저 하는가?
  - 레포 용어(라벨/기능명)를 정확히 쓰는가?
- 운영 지표
  - 처리 시간(원시 JSON 수 대비), 실패율, 중복/누락률(간단한 무결성 체크)

---

## 10) 리스크/대응

- **표본 편향**: “최근 2주”만 보면 장기 정책을 왜곡할 수 있음  
  → 기간을 슬라이딩 윈도우로 확장/비교(2주 vs 3개월) 옵션 제공
- **Closed 사유의 다양성**: 단일 규칙으로 일반화 위험  
  → 인사이트는 “빈도/최근성/예외”를 함께 기록하고, 프롬프트에는 상위 규칙만 반영
- **데이터 누락**: no-hydrate 모드에서는 댓글/리뷰 정보가 부족  
  → 프롬프트 업데이트 시 “신뢰도 레벨”을 낮추고, 부족한 입력을 명시

---

## 11) 구현 로드맵(제안)

### Phase 1 (현재 레포 범위 내)
- `raw_http` → 파생 CSV/JSON 뷰 확장(`repo_work_item*` 계열)
- `repo_insights.json/.md` 생성(근거 링크 포함)
- `AGENTS_SUMMARY.md` 파서 + 프롬프트 업데이트 산출물 생성
- `unittest`로 “인사이트 추출 규칙” 회귀 테스트 추가

### Phase 2 (정책 문서 + 코드 레벨 컨텍스트)
- 레포의 `README/CONTRIBUTING/CODEOWNERS`를 함께 인사이트로 통합
- 파일 경로 기반으로 “변경 핫스팟”을 DevRel 가이드에 반영

### Phase 3 (운영 적용)
- 업데이트된 프롬프트를 실제 DevRel 워크플로우(응답 생성, 문서 갱신)에서 A/B로 검증
- 인간 리뷰/승인 프로세스(승인 없이는 배포 금지) 고정
