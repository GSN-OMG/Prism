# Phase 2: DevRel Agent Pipeline

Phase 2는 GitHub 이슈를 분석하고 처리하는 5개의 AI 에이전트 파이프라인과 Human-in-the-Loop 피드백 시스템을 제공합니다.

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Phase 2: Agent Pipeline                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │   Phase 1    │───▶│  GitHub API  │───▶│ Issue Input  │               │
│  │ Issue Trigger│    │   Webhook    │    │              │               │
│  └──────────────┘    └──────────────┘    └──────┬───────┘               │
│                                                  │                       │
│                                                  ▼                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Agent Pipeline (5 Agents)                     │    │
│  │                                                                  │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐     │    │
│  │  │  Issue    │  │Assignment │  │ Response  │  │ Docs Gap  │     │    │
│  │  │ Analysis  │─▶│  Agent    │─▶│  Agent    │─▶│  Agent    │     │    │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘     │    │
│  │        │              │              │              │            │    │
│  │        └──────────────┴──────────────┴──────────────┘            │    │
│  │                              │                                   │    │
│  │                              ▼                                   │    │
│  │                      ┌───────────┐                               │    │
│  │                      │ Promotion │                               │    │
│  │                      │  Agent    │                               │    │
│  │                      └───────────┘                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                  │                                       │
│                                  ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Human-in-the-Loop Review                      │    │
│  │  - Agent 결과 검토                                                │    │
│  │  - 승인/거절 + 피드백                                             │    │
│  │  - Decision Trace 확인                                           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                  │                                       │
│                                  ▼                                       │
│                         ┌──────────────┐                                │
│                         │   Phase 3    │                                │
│                         │  Agent Critic│                                │
│                         └──────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘
```

## 디렉토리 구조

```
phase2/prism-devrel/
├── src/devrel/
│   ├── agents/           # 5개 AI 에이전트
│   │   ├── assignment.py # Issue 분석 + 담당자 할당
│   │   ├── docs.py       # 문서 갭 분석
│   │   ├── promotion.py  # 기여자 승격 평가
│   │   ├── response.py   # 응답 생성
│   │   └── types.py      # 공유 타입 정의
│   ├── llm/              # LLM 클라이언트
│   │   ├── client.py     # OpenAI API 래퍼
│   │   └── model_selector.py
│   └── search/           # 외부 API 클라이언트
│       ├── github_client.py  # GitHub API
│       └── tavily_client.py  # Tavily Search API
├── web/                  # Next.js 프론트엔드
│   └── src/
│       ├── app/          # App Router
│       │   ├── api/      # API Routes
│       │   └── page.tsx  # 메인 대시보드
│       ├── components/   # React 컴포넌트
│       ├── lib/          # 유틸리티
│       └── types/        # TypeScript 타입
├── tests/                # 테스트
├── raw_data/             # CSV 데이터
├── docs/                 # 문서
└── results/              # 실행 결과
```

## 빠른 시작

### 1. 환경 설정

```bash
cd phase2/prism-devrel

# Python 환경
pip install -e .

# 환경 변수 (.env)
cp .env.example .env
# OPENAI_API_KEY, GITHUB_TOKEN, TAVILY_API_KEY 설정
```

### 2. Python 에이전트 실행

```bash
# 테스트 실행
python -m pytest

# Fixture 기반 실행
python scripts/run_fixtures.py

# LLM 실제 호출 (과금 발생)
USE_LLM=1 python scripts/run_fixtures.py
```

### 3. Web UI 실행

```bash
cd web
npm install
npm run dev
# http://localhost:3000 접속
```

## 5개 에이전트

| 에이전트 | 역할 | 입력 | 출력 |
|---------|------|------|------|
| **Issue Analysis** | 이슈 분류/우선순위 | Issue | `IssueAnalysisOutput` |
| **Assignment** | 담당자 추천 | Issue + Analysis | `AssignmentOutput` |
| **Response** | 응답 전략/텍스트 | Issue + Analysis | `ResponseOutput` |
| **Docs Gap** | 문서 갭 탐지 | Issues[] | `DocGapOutput` |
| **Promotion** | 기여자 승격 평가 | Contributor | `PromotionOutput` |

자세한 내용: [docs/agents.md](docs/agents.md)

## API 엔드포인트

| 엔드포인트 | 메소드 | 설명 |
|-----------|--------|------|
| `/api/issues` | GET | GitHub 이슈 목록 조회 |
| `/api/agents/run` | POST | 에이전트 실행 |
| `/api/contributors` | GET | 기여자 평가 목록 |

자세한 내용: [docs/api.md](docs/api.md)

## Phase 연동

### Phase 1 → Phase 2
```typescript
// Phase 1에서 이슈 트리거
const response = await fetch('/api/agents/run', {
  method: 'POST',
  body: JSON.stringify({
    issue: githubIssue,
    agent: 'issue_analysis'
  })
});
```

### Phase 2 → Phase 3
```typescript
// Phase 2 완료 후 Phase 3로 전달
const pipelineResult = {
  issue: selectedIssue,
  agentResults: pipeline.agents,
  feedbacks: pipeline.feedbacks
};
// Phase 3 Critic 에이전트로 전달
```

자세한 내용: [docs/integration.md](docs/integration.md)

## 핵심 타입

```typescript
// 이슈 파이프라인 상태
interface IssuePipelineState {
  issue: GitHubIssue;
  agents: Record<AgentType, AgentResult>;
  overallProgress: number;
  status: 'idle' | 'running' | 'awaiting_feedback' | 'completed';
  feedbacks: HumanFeedback[];
}

// 에이전트 실행 결과
interface AgentResult {
  agent: AgentType;
  status: AgentStatus;
  output?: AgentOutput;
  decisionTrace?: DecisionStep[];
  durationMs?: number;
}

// Human-in-the-Loop 피드백
interface HumanFeedback {
  agent: AgentType;
  approved: boolean;
  comment: string;
  reviewer: string;
  timestamp: string;
}
```

## 문서

- [에이전트 상세](docs/agents.md) - 5개 에이전트 상세 설명
- [API 레퍼런스](docs/api.md) - Python/Web API 문서
- [웹 프론트엔드](docs/web.md) - Next.js UI 컴포넌트
- [연동 가이드](docs/integration.md) - Phase 1, 3 연동 방법

## 환경 변수

| 변수 | 필수 | 설명 |
|-----|------|------|
| `OPENAI_API_KEY` | Yes | OpenAI API 키 |
| `GITHUB_TOKEN` | No | GitHub API 토큰 |
| `TAVILY_API_KEY` | No | Tavily Search API 키 |
| `USE_LLM` | No | LLM 실제 호출 활성화 |

## 라이선스

Private - Hackathon Project
