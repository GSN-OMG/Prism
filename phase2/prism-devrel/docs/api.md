# Phase 2 API 레퍼런스

이 문서는 Phase 2의 Python 백엔드 API와 Web API 엔드포인트를 설명합니다.

## Python API

### LLM Client

**파일**: `src/devrel/llm/client.py`

OpenAI API를 래핑한 LLM 클라이언트입니다.

```python
from devrel.llm.client import LlmClient, JsonSchema

# 클라이언트 초기화
client = LlmClient(api_key="sk-...")

# JSON 스키마 정의
schema = JsonSchema(
    name="issue_analysis",
    schema={
        "type": "object",
        "properties": {
            "issue_type": {"type": "string"},
            "priority": {"type": "string"}
        },
        "required": ["issue_type", "priority"]
    }
)

# 구조화된 출력 생성
result = client.generate_json(
    task=LlmTask.ISSUE_TRIAGE,
    system="You are a DevRel agent...",
    user="Analyze this issue...",
    json_schema=schema
)
```

### LLM Task Types

```python
from devrel.llm.model_selector import LlmTask

class LlmTask(str, Enum):
    ISSUE_TRIAGE = "issue_triage"    # 이슈 분류
    ASSIGNMENT = "assignment"         # 담당자 할당
    RESPONSE = "response"             # 응답 생성
    DOCS = "docs"                     # 문서 갭 분석
    PROMOTION = "promotion"           # 승격 평가
```

---

### GitHub Client

**파일**: `src/devrel/search/github_client.py`

GitHub API를 통한 문서 구조 조회 및 비교를 제공합니다.

```python
from devrel.search.github_client import GitHubClient

# 클라이언트 초기화 (GITHUB_TOKEN 환경변수 또는 직접 전달)
client = GitHubClient(token="ghp_...")

# 유사 레포 검색
repos = client.search_similar_repos(
    topic="redis caching",
    language="python"
)
# ['redis/redis-py', 'django/django', ...]

# 문서 구조 조회
docs_info = client.get_docs_structure("openai/openai-agents-python")
# RepoDocsInfo(
#     repo="openai/openai-agents-python",
#     docs_path="docs",
#     files=[RepoDocFile(...)],
#     topics=["getting-started", "api-reference", ...],
#     total_files=15
# )

# 문서 구조 비교
comparison = client.compare_docs(
    target_repo="my-org/my-repo",
    reference_repo="openai/openai-agents-python"
)
# DocsComparisonResult(
#     missing_topics=["quickstart", "troubleshooting"],
#     coverage_ratio=0.65,
#     suggestions=[...]
# )
```

---

### Tavily Client

**파일**: `src/devrel/search/tavily_client.py`

Tavily Search API를 통한 외부 인사이트 검색을 제공합니다.

```python
from devrel.search.tavily_client import TavilyClient

# 클라이언트 초기화 (TAVILY_API_KEY 환경변수 또는 직접 전달)
client = TavilyClient(api_key="tvly-...")

# 이슈 컨텍스트 검색
insight = client.search_issue_context(
    issue_title="Redis connection timeout",
    issue_body="Getting timeout errors...",
    repo_name="my-org/my-repo"
)
# SearchInsight(
#     query="...",
#     results=[SearchResult(title, url, content, score), ...],
#     answer="Based on the search...",
#     related_repos=["redis/redis-py", ...]
# )

# 유사 레포 검색
similar = client.search_similar_repos(
    repo_name="my-org/my-repo",
    topic="caching documentation"
)

# 문서 베스트 프랙티스 검색
best = client.search_docs_best_practices(
    topic="redis",
    repo_type="python agent framework"
)
```

---

## Web API Endpoints

### GET /api/issues

GitHub 레포지토리의 이슈 목록을 조회합니다.

**Request:**
```
GET /api/issues
```

**Response:**
```json
[
  {
    "number": 1,
    "title": "Add support for Redis caching",
    "body": "We need to add Redis caching support...",
    "labels": ["feature", "enhancement"],
    "state": "open",
    "created_at": "2024-01-15T10:30:00Z",
    "user": {
      "login": "username",
      "avatar_url": "https://avatars.githubusercontent.com/u/1"
    },
    "html_url": "https://github.com/GSN-OMG/Prism/issues/1"
  }
]
```

**환경 변수:**
- `GITHUB_TOKEN`: GitHub API 인증 (선택)

---

### POST /api/agents/run

특정 에이전트를 실행합니다.

**Request:**
```json
POST /api/agents/run
Content-Type: application/json

{
  "issue": {
    "number": 1,
    "title": "Bug: Authentication fails",
    "body": "When using special characters...",
    "labels": ["bug", "critical"],
    "state": "open",
    "created_at": "2024-01-15T10:30:00Z",
    "user": {
      "login": "reporter",
      "avatar_url": "..."
    },
    "html_url": "..."
  },
  "agent": "issue_analysis"
}
```

**Agent Types:**
- `issue_analysis` - 이슈 분석
- `assignment` - 담당자 할당
- `response` - 응답 생성
- `docs_gap` - 문서 갭 탐지
- `promotion` - 승격 평가

**Response:**
```json
{
  "agent": "issue_analysis",
  "status": "completed",
  "startTime": "2024-01-15T10:30:00.000Z",
  "endTime": "2024-01-15T10:30:02.500Z",
  "durationMs": 2500,
  "output": {
    "issue_type": "bug",
    "priority": "critical",
    "required_skills": ["auth", "debugging"],
    "keywords": ["authentication", "special characters"],
    "summary": "Authentication fails with special characters",
    "needs_more_info": false,
    "suggested_action": "direct_answer"
  },
  "decisionTrace": [
    {
      "step_number": 1,
      "step_name": "Parse Issue Content",
      "input": { "title": "...", "labels": ["bug"] },
      "output": { "parsed": true },
      "reasoning": "Extracted title, body, and labels",
      "timestamp": "2024-01-15T10:30:00.500Z"
    }
  ]
}
```

---

### GET /api/contributors

기여자 목록과 승격 평가 결과를 조회합니다.

**Request:**
```
GET /api/contributors
```

**Response:**
```json
[
  {
    "contributor": {
      "login": "username",
      "areas": ["code-review", "development"],
      "recent_activity_score": 1.5,
      "merged_prs": 9,
      "reviews": 5
    },
    "evaluation": {
      "is_candidate": true,
      "current_stage": "REGULAR",
      "suggested_stage": "CORE",
      "confidence": 0.85,
      "evidence": [...],
      "recommendation": "Promote to Core..."
    },
    "decision_steps": [...],
    "insights": [...],
    "total_duration_ms": 150,
    "model_used": "rule-based"
  }
]
```

---

## 타입 정의 (TypeScript)

### GitHubIssue

```typescript
interface GitHubIssue {
  number: number;
  title: string;
  body: string;
  labels: string[];
  state: 'open' | 'closed';
  created_at: string;
  user: {
    login: string;
    avatar_url: string;
  };
  html_url: string;
}
```

### AgentResult

```typescript
interface AgentResult {
  agent: AgentType;
  status: 'pending' | 'running' | 'completed' | 'error';
  startTime?: string;
  endTime?: string;
  durationMs?: number;
  output?: IssueAnalysisOutput | AssignmentOutput | ResponseOutput | DocGapOutput | PromotionOutput;
  error?: string;
  decisionTrace?: DecisionStep[];
}
```

### DecisionStep

```typescript
interface DecisionStep {
  step_number: number;
  step_name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  reasoning: string;
  timestamp: string;
}
```

---

## 에러 처리

### HTTP Status Codes

| 코드 | 설명 |
|-----|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (필수 파라미터 누락) |
| 500 | 서버 에러 (에이전트 실행 실패) |

### 에러 응답 형식

```json
{
  "error": "Agent execution failed",
  "details": "Invalid issue format"
}
```

---

## 환경 변수

| 변수 | 필수 | 기본값 | 설명 |
|-----|------|-------|------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API 키 |
| `GITHUB_TOKEN` | No | - | GitHub API 토큰 (rate limit 증가) |
| `TAVILY_API_KEY` | No | - | Tavily Search API 키 |
| `USE_LLM` | No | `false` | LLM 실제 호출 활성화 |

---

## 사용 예시

### Python에서 에이전트 체이닝

```python
from devrel.agents.assignment import analyze_issue, recommend_assignee, Issue
from devrel.agents.response import generate_response_llm
from devrel.llm.client import LlmClient

# 1. 이슈 분석
issue = Issue(number=1, title="...", body="...", labels=("bug",))
analysis = analyze_issue(issue)

# 2. 담당자 추천
contributors = load_contributors()
assignment = recommend_assignee(analysis, contributors)

# 3. 응답 생성 (LLM 사용)
llm = LlmClient()
response = generate_response_llm(llm, issue=issue, issue_analysis=analysis)
```

### JavaScript/TypeScript에서 API 호출

```typescript
// 이슈 목록 조회
const issues = await fetch('/api/issues').then(r => r.json());

// 에이전트 실행
const result = await fetch('/api/agents/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    issue: issues[0],
    agent: 'issue_analysis'
  })
}).then(r => r.json());

console.log(result.output.issue_type);  // 'bug'
console.log(result.decisionTrace);      // [{ step_number: 1, ... }]
```
