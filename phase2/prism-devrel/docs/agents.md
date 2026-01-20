# Phase 2 에이전트 상세 문서

이 문서는 Phase 2의 5개 AI 에이전트에 대한 상세 설명을 제공합니다.

## 에이전트 개요

```
┌──────────────────────────────────────────────────────────────────┐
│                        Agent Pipeline                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   Issue Input                                                     │
│       │                                                           │
│       ▼                                                           │
│   ┌─────────────────┐                                            │
│   │ Issue Analysis  │ ◀── 분류, 우선순위, 키워드 추출             │
│   └────────┬────────┘                                            │
│            │                                                      │
│       ┌────┴────┐                                                │
│       ▼         ▼                                                │
│  ┌──────────┐ ┌──────────┐                                       │
│  │Assignment│ │ Response │ ◀── 담당자 추천, 응답 생성            │
│  └────┬─────┘ └────┬─────┘                                       │
│       │            │                                              │
│       └─────┬──────┘                                             │
│             ▼                                                     │
│      ┌───────────┐                                               │
│      │ Docs Gap  │ ◀── 문서 갭 탐지 (다중 이슈 분석)             │
│      └─────┬─────┘                                               │
│            │                                                      │
│            ▼                                                      │
│      ┌───────────┐                                               │
│      │ Promotion │ ◀── 기여자 승격 평가                          │
│      └───────────┘                                               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Issue Analysis Agent

**파일**: `src/devrel/agents/assignment.py`

GitHub 이슈를 분석하여 유형, 우선순위, 필요 스킬 등을 파악합니다.

### 입력 (Input)

```python
@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str
    labels: tuple[str, ...] = ()
```

### 출력 (Output)

```python
@dataclass(frozen=True, slots=True)
class IssueAnalysisOutput:
    issue_type: IssueType        # bug, feature, question, documentation, other
    priority: Priority           # critical, high, medium, low
    required_skills: tuple[str, ...]  # ['auth', 'cache', 'docs']
    keywords: tuple[str, ...]    # ['redis', 'logging', 'oauth']
    summary: str
    needs_more_info: bool
    suggested_action: ResponseStrategy  # direct_answer, request_info, link_docs, escalate
```

### 함수

```python
# Rule-based 분석
def analyze_issue(issue: Issue) -> IssueAnalysisOutput

# LLM 기반 분석
def analyze_issue_llm(llm: LlmClient, issue: Issue) -> IssueAnalysisOutput

# Tavily 외부 검색 포함 분석
def analyze_issue_with_tavily(
    llm: LlmClient,
    issue: Issue,
    repo_name: str,
    tavily_api_key: str | None = None
) -> EnhancedIssueAnalysis
```

### 사용 예시

```python
from devrel.agents.assignment import analyze_issue, Issue

issue = Issue(
    number=42,
    title="Bug: Authentication fails with special characters",
    body="When using @ in password, login fails...",
    labels=("bug", "critical")
)

analysis = analyze_issue(issue)
# IssueAnalysisOutput(
#     issue_type=IssueType.BUG,
#     priority=Priority.CRITICAL,
#     required_skills=('auth', 'debugging'),
#     ...
# )
```

---

## 2. Assignment Agent

**파일**: `src/devrel/agents/assignment.py`

이슈 분석 결과와 기여자 정보를 기반으로 최적의 담당자를 추천합니다.

### 입력 (Input)

```python
@dataclass(frozen=True, slots=True)
class Contributor:
    login: str
    areas: tuple[str, ...] = ()        # ['auth', 'cache', 'docs']
    recent_activity_score: float = 0.0
    merged_prs: int = 0
    reviews: int = 0
    first_contribution_date: str | None = None
    last_contribution_date: str | None = None
```

### 출력 (Output)

```python
@dataclass(frozen=True, slots=True)
class AssignmentOutput:
    recommended_assignee: str          # 'username'
    confidence: float                  # 0.0 ~ 1.0
    reasons: tuple[AssignmentReason, ...]
    context_for_assignee: str
    alternative_assignees: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class AssignmentReason:
    factor: str           # 'skill_match', 'recent_activity', 'merged_prs'
    explanation: str
    score: float         # 0.0 ~ 1.0
```

### 함수

```python
# Rule-based 추천
def recommend_assignee(
    issue_analysis: IssueAnalysisOutput,
    contributors: list[Contributor],
    *,
    limit: int = 3
) -> AssignmentOutput

# LLM 기반 추천
def recommend_assignee_llm(
    llm: LlmClient,
    *,
    issue: Issue,
    issue_analysis: IssueAnalysisOutput,
    contributors: list[Contributor],
    limit: int = 3
) -> AssignmentOutput
```

### 스코어링 로직

```python
def _score_contributor(issue_analysis, contributor):
    score = min(contributor.recent_activity_score, 2.0)

    # 스킬 매칭
    required = set(issue_analysis.required_skills)
    areas = set(contributor.areas)
    overlap = len(required & areas)
    score += overlap * 2.0

    # PR/리뷰 가중치
    score += min(contributor.merged_prs, 10) * 0.05
    score += min(contributor.reviews, 20) * 0.02

    return score
```

---

## 3. Response Agent

**파일**: `src/devrel/agents/response.py`

이슈에 대한 적절한 응답 전략과 텍스트를 생성합니다.

### 출력 (Output)

```python
@dataclass(frozen=True, slots=True)
class ResponseOutput:
    strategy: ResponseStrategy    # direct_answer, request_info, link_docs, escalate
    response_text: str
    confidence: float
    references: tuple[str, ...]   # 관련 문서/링크
    follow_up_needed: bool
```

### 응답 전략

| 전략 | 설명 | 트리거 조건 |
|-----|------|------------|
| `direct_answer` | 직접 답변 | 명확한 버그/기능 요청 |
| `request_info` | 추가 정보 요청 | `needs_more_info=true` |
| `link_docs` | 문서 링크 제공 | question 타입 이슈 |
| `escalate` | 상위 에스컬레이션 | critical 우선순위 |

### 함수

```python
# LLM 기반 응답 생성
def generate_response_llm(
    llm: LlmClient,
    *,
    issue: Issue,
    issue_analysis: IssueAnalysisOutput
) -> ResponseOutput
```

---

## 4. Docs Gap Agent

**파일**: `src/devrel/agents/docs.py`

여러 이슈를 분석하여 문서화가 필요한 영역을 탐지합니다.

### 출력 (Output)

```python
@dataclass(frozen=True, slots=True)
class DocGapOutput:
    has_gap: bool
    gap_topic: str               # 'redis', 'logging', 'authentication'
    affected_issues: tuple[int, ...]  # [1, 5, 12]
    suggested_doc_path: str      # 'docs/cache/redis.md'
    suggested_outline: tuple[str, ...]
    priority: Priority
```

### 확장 출력 (GitHub + Tavily)

```python
@dataclass(frozen=True, slots=True)
class FullDocGapAnalysis:
    gap_analysis: DocGapOutput
    # GitHub API 결과
    docs_comparison: DocsComparisonResult | None
    reference_examples: tuple[RepoDocFile, ...]
    # Tavily 결과
    tavily_insights: tuple[ExternalDocReference, ...]
    best_practices: str | None
    tavily_answer: str | None
    # 종합 제안
    suggested_structure: tuple[str, ...]
    action_items: tuple[str, ...]
```

### 함수

```python
# Rule-based 갭 탐지
def detect_doc_gaps(issues: list[Issue]) -> list[DocGapCandidate]

# LLM 기반 갭 탐지
def detect_doc_gaps_llm(llm: LlmClient, issues: list[Issue]) -> DocGapOutput

# GitHub API + 문서 비교
def detect_doc_gaps_with_github(
    llm: LlmClient,
    issues: list[Issue],
    target_repo: str,
    reference_repos: list[str] | None = None,
    github_token: str | None = None
) -> GitHubEnhancedDocGapOutput

# 전체 분석 (GitHub + Tavily)
def detect_doc_gaps_full(
    llm: LlmClient,
    issues: list[Issue],
    target_repo: str,
    reference_repos: list[str] | None = None,
    github_token: str | None = None,
    tavily_api_key: str | None = None
) -> FullDocGapAnalysis
```

---

## 5. Promotion Agent

**파일**: `src/devrel/agents/promotion.py`

기여자의 활동을 평가하여 승격 대상인지 판단합니다.

### 출력 (Output)

```python
@dataclass(frozen=True, slots=True)
class PromotionOutput:
    is_candidate: bool           # 승격 대상 여부
    current_stage: str           # 'NEW', 'FIRST_TIMER', 'REGULAR', 'CORE', 'MAINTAINER'
    suggested_stage: str
    confidence: float
    evidence: tuple[PromotionEvidence, ...]
    recommendation: str

@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    criterion: str    # 'development_path', 'reviewer_path', 'balanced_path'
    status: str       # 'met', 'not_met', 'exceeds', 'moderate'
    detail: str
```

### 승격 경로 (Multi-path Promotion)

| 경로 | 조건 | 설명 |
|-----|------|------|
| **Development** | 8+ merged PRs | 코드 기여 중심 |
| **Reviewer** | 8+ code reviews | 리뷰 활동 중심 |
| **Balanced** | 3+ PRs AND 5+ reviews | 균형잡힌 기여 |

### 단계 (Stages)

```python
STAGES = {
    'NEW':        { 'order': 0, 'minPRs': 0  },
    'FIRST_TIMER': { 'order': 1, 'minPRs': 1  },
    'REGULAR':    { 'order': 2, 'minPRs': 2  },
    'CORE':       { 'order': 3, 'minPRs': 8  },
    'MAINTAINER': { 'order': 4, 'minPRs': 20 },
}
```

### 함수

```python
# Rule-based 평가
def evaluate_promotion(contributor: Contributor) -> PromotionOutput

# LLM 기반 평가
def evaluate_promotion_llm(
    llm: LlmClient,
    contributor: Contributor
) -> PromotionOutput
```

---

## Decision Trace (의사결정 추적)

모든 에이전트는 투명성을 위해 Decision Trace를 생성합니다.

```python
@dataclass(frozen=True, slots=True)
class DecisionStep:
    step_number: int
    step_name: str
    input: dict[str, object]
    output: dict[str, object]
    reasoning: str
    timestamp: str
```

### 예시 (Promotion Agent)

```json
[
  {
    "step_number": 1,
    "step_name": "Load Contributor Data",
    "input": { "login": "username" },
    "output": { "merged_prs": 9, "reviews": 0 },
    "reasoning": "Loaded metrics for contributor @username from raw_data"
  },
  {
    "step_number": 2,
    "step_name": "Infer Current Stage",
    "input": { "merged_prs": 9 },
    "output": { "current_stage": "CORE" },
    "reasoning": "With 9 merged PRs, contributor qualifies for Core stage"
  },
  {
    "step_number": 3,
    "step_name": "Evaluate Promotion Paths",
    "output": {
      "path_development": { "met": true },
      "path_reviewer": { "met": false },
      "path_balanced": { "met": false }
    },
    "reasoning": "Qualifies via development path (8+ PRs)"
  }
]
```

---

## 타입 정의 파일

모든 공유 타입은 `src/devrel/agents/types.py`에 정의되어 있습니다.

주요 enum:

```python
class IssueType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"
    DOCUMENTATION = "documentation"
    OTHER = "other"

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ResponseStrategy(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    REQUEST_INFO = "request_info"
    LINK_DOCS = "link_docs"
    ESCALATE = "escalate"
```
