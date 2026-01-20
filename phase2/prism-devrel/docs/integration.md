# Phase 연동 가이드

이 문서는 Phase 2를 Phase 1 및 Phase 3와 연동하는 방법을 설명합니다.

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Prism System                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐        │
│  │   Phase 1   │────────▶│   Phase 2   │────────▶│   Phase 3   │        │
│  │ Issue Entry │         │ Agent Work  │         │ Agent Critic│        │
│  └─────────────┘         └─────────────┘         └─────────────┘        │
│        │                       │                       │                 │
│        │                       │                       │                 │
│        ▼                       ▼                       ▼                 │
│   GitHub Issue           Agent Results            Critic Debate          │
│   Webhook/UI             + Human Feedback         + Final Decision       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 → Phase 2 연동

### 입력 데이터 구조

Phase 1에서 Phase 2로 전달되는 GitHub 이슈 형식:

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

### 연동 방법 1: Webhook

Phase 1에서 GitHub Webhook을 수신하면 Phase 2 API를 호출합니다.

```typescript
// Phase 1: GitHub Webhook 핸들러
async function handleGitHubWebhook(payload: WebhookPayload) {
  if (payload.action !== 'opened') return;

  const issue: GitHubIssue = {
    number: payload.issue.number,
    title: payload.issue.title,
    body: payload.issue.body || '',
    labels: payload.issue.labels.map(l => l.name),
    state: payload.issue.state,
    created_at: payload.issue.created_at,
    user: {
      login: payload.issue.user.login,
      avatar_url: payload.issue.user.avatar_url,
    },
    html_url: payload.issue.html_url,
  };

  // Phase 2 파이프라인 트리거
  await triggerPhase2Pipeline(issue);
}

async function triggerPhase2Pipeline(issue: GitHubIssue) {
  const PHASE2_URL = process.env.PHASE2_API_URL || 'http://localhost:3000';

  // 순차적으로 에이전트 실행
  const agents = ['issue_analysis', 'assignment', 'response', 'docs_gap', 'promotion'];

  const results = {};
  for (const agent of agents) {
    const response = await fetch(`${PHASE2_URL}/api/agents/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ issue, agent }),
    });
    results[agent] = await response.json();
  }

  return results;
}
```

### 연동 방법 2: 직접 UI 연결

Phase 1 UI에서 직접 Phase 2 웹 페이지로 이동:

```typescript
// Phase 1: 이슈 클릭 시 Phase 2로 이동
function handleIssueClick(issue: GitHubIssue) {
  const params = new URLSearchParams({
    issue: JSON.stringify(issue),
  });
  window.location.href = `/phase2?${params}`;
}
```

### 연동 방법 3: 공유 상태 (권장)

공유 상태 저장소를 사용하여 Phase 간 데이터 전달:

```typescript
// 공유 타입 (phases/shared/types.ts)
interface PipelineState {
  phase1: {
    triggeredAt: string;
    issue: GitHubIssue;
  };
  phase2?: {
    startedAt: string;
    completedAt?: string;
    agents: Record<AgentType, AgentResult>;
    feedbacks: HumanFeedback[];
  };
  phase3?: {
    startedAt: string;
    criticResults: CriticResult[];
    finalDecision: FinalDecision;
  };
}

// 상태 저장 (Redis, DB, 또는 메모리)
async function savePipelineState(issueNumber: number, state: PipelineState) {
  await redis.set(`pipeline:${issueNumber}`, JSON.stringify(state));
}

async function getPipelineState(issueNumber: number): Promise<PipelineState | null> {
  const data = await redis.get(`pipeline:${issueNumber}`);
  return data ? JSON.parse(data) : null;
}
```

---

## Phase 2 → Phase 3 연동

### 출력 데이터 구조

Phase 2가 완료되면 Phase 3로 전달되는 데이터:

```typescript
interface Phase2Output {
  issue: GitHubIssue;
  agentResults: {
    issue_analysis: AgentResult;
    assignment: AgentResult;
    response: AgentResult;
    docs_gap: AgentResult;
    promotion: AgentResult;
  };
  feedbacks: HumanFeedback[];
  metadata: {
    startTime: string;
    endTime: string;
    totalDurationMs: number;
  };
}
```

### 연동 방법 1: 완료 콜백

Phase 2에서 모든 피드백이 완료되면 Phase 3를 트리거:

```typescript
// Phase 2: 피드백 완료 시 Phase 3 트리거
function handleAllFeedbacksCompleted(pipeline: IssuePipelineState) {
  const phase2Output: Phase2Output = {
    issue: pipeline.issue,
    agentResults: pipeline.agents,
    feedbacks: pipeline.feedbacks,
    metadata: {
      startTime: pipeline.startTime!,
      endTime: new Date().toISOString(),
      totalDurationMs: calculateDuration(pipeline),
    },
  };

  // Phase 3로 전달
  triggerPhase3Critic(phase2Output);
}

async function triggerPhase3Critic(output: Phase2Output) {
  const PHASE3_URL = process.env.PHASE3_API_URL || 'http://localhost:3001';

  await fetch(`${PHASE3_URL}/api/critic/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(output),
  });
}
```

### 연동 방법 2: 이벤트 기반

이벤트 버스를 통한 Phase 간 통신:

```typescript
// 이벤트 타입
type PipelineEvent =
  | { type: 'PHASE1_ISSUE_CREATED'; issue: GitHubIssue }
  | { type: 'PHASE2_STARTED'; issueNumber: number }
  | { type: 'PHASE2_AGENT_COMPLETED'; issueNumber: number; agent: AgentType; result: AgentResult }
  | { type: 'PHASE2_FEEDBACK_SUBMITTED'; issueNumber: number; feedback: HumanFeedback }
  | { type: 'PHASE2_COMPLETED'; output: Phase2Output }
  | { type: 'PHASE3_CRITIC_STARTED'; issueNumber: number }
  | { type: 'PHASE3_COMPLETED'; decision: FinalDecision };

// 이벤트 발행
function emitEvent(event: PipelineEvent) {
  eventBus.emit('pipeline', event);
}

// Phase 3에서 이벤트 수신
eventBus.on('pipeline', (event: PipelineEvent) => {
  if (event.type === 'PHASE2_COMPLETED') {
    startCriticDebate(event.output);
  }
});
```

---

## Phase 3 입력 형식

Phase 3 Critic 에이전트가 기대하는 입력:

```typescript
interface CriticInput {
  // Phase 2 결과
  phase2Output: Phase2Output;

  // Critic 설정
  config: {
    debateRounds: number;       // 토론 라운드 수
    agentsToDebate: AgentType[];  // 토론 대상 에이전트
    consensusThreshold: number;  // 합의 기준 (0-1)
  };
}

interface CriticResult {
  agent: AgentType;
  originalOutput: AgentResult['output'];
  criticFeedback: string;
  suggestedChanges: string[];
  confidenceChange: number;  // -1 ~ +1
  approved: boolean;
}

interface FinalDecision {
  issueNumber: number;
  recommendations: {
    assignee: string;
    responseStrategy: string;
    docGapAction: string;
    promotionDecision: boolean;
  };
  reasoning: string;
  consensusReached: boolean;
}
```

---

## 공유 타입 파일

모든 Phase에서 사용하는 공유 타입을 별도 패키지로 관리하는 것을 권장합니다:

```
phases/
├── shared/
│   ├── types/
│   │   ├── github.ts      # GitHubIssue, etc.
│   │   ├── agents.ts      # AgentType, AgentResult, etc.
│   │   ├── feedback.ts    # HumanFeedback
│   │   └── pipeline.ts    # PipelineState
│   └── package.json
├── phase1/
├── phase2/
└── phase3/
```

```json
// phases/shared/package.json
{
  "name": "@prism/shared-types",
  "version": "1.0.0",
  "main": "dist/index.js",
  "types": "dist/index.d.ts"
}
```

```typescript
// 각 Phase에서 import
import { GitHubIssue, AgentResult, HumanFeedback } from '@prism/shared-types';
```

---

## API 엔드포인트 요약

### Phase 2가 제공하는 API

| 엔드포인트 | 메소드 | 설명 | Phase 1 사용 | Phase 3 사용 |
|-----------|--------|------|-------------|-------------|
| `/api/issues` | GET | 이슈 목록 | ○ | - |
| `/api/agents/run` | POST | 에이전트 실행 | ○ | - |
| `/api/contributors` | GET | 기여자 평가 | - | ○ |

### Phase 2가 호출하는 API

| 대상 | 엔드포인트 | 설명 |
|-----|-----------|------|
| Phase 3 | `/api/critic/start` | Critic 토론 시작 |
| Phase 3 | `/api/critic/status` | 토론 상태 조회 |

---

## 환경 변수

```env
# Phase 2 .env
PHASE1_WEBHOOK_SECRET=xxx     # Phase 1 Webhook 시크릿
PHASE3_API_URL=http://localhost:3001  # Phase 3 API URL

# 공통
OPENAI_API_KEY=sk-xxx
GITHUB_TOKEN=ghp-xxx
REDIS_URL=redis://localhost:6379  # 공유 상태 저장소 (옵션)
```

---

## 연동 체크리스트

### Phase 1 → Phase 2
- [ ] GitHub Webhook 설정
- [ ] Issue 형식 변환 확인
- [ ] Phase 2 API URL 설정
- [ ] 에러 핸들링 (Phase 2 다운 시)

### Phase 2 → Phase 3
- [ ] 완료 콜백/이벤트 설정
- [ ] Phase2Output 형식 확인
- [ ] Phase 3 API URL 설정
- [ ] 피드백 데이터 포함 확인

### 공통
- [ ] 공유 타입 정의
- [ ] 로깅/모니터링 설정
- [ ] 타임아웃 처리
- [ ] 재시도 로직

---

## 디버깅 팁

### 연동 테스트

```bash
# Phase 2 단독 테스트
curl -X POST http://localhost:3000/api/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "issue": {
      "number": 1,
      "title": "Test issue",
      "body": "Test body",
      "labels": ["bug"],
      "state": "open",
      "created_at": "2024-01-01T00:00:00Z",
      "user": {"login": "test", "avatar_url": ""},
      "html_url": ""
    },
    "agent": "issue_analysis"
  }'
```

### 로그 확인

```typescript
// Phase 2에서 연동 로그
console.log('[Phase2] Received from Phase1:', JSON.stringify(issue));
console.log('[Phase2] Sending to Phase3:', JSON.stringify(output));
```
