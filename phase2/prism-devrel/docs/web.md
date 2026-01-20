# Phase 2 Web Frontend 문서

이 문서는 Phase 2의 Next.js 기반 웹 프론트엔드를 설명합니다.

## 기술 스택

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: React useState/useEffect

## 프로젝트 구조

```
web/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── agents/run/route.ts   # 에이전트 실행 API
│   │   │   ├── contributors/route.ts  # 기여자 목록 API
│   │   │   └── issues/route.ts       # GitHub 이슈 API
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx                  # 메인 대시보드
│   ├── components/
│   │   ├── AgentCard.tsx             # 에이전트 상태 카드
│   │   ├── AgentOutputModal.tsx      # 에이전트 출력 모달
│   │   ├── AgentPipeline.tsx         # 파이프라인 전체 뷰
│   │   ├── ContributorCard.tsx       # 기여자 카드 (승격 평가)
│   │   ├── DecisionTrace.tsx         # 의사결정 추적 뷰
│   │   ├── EvidenceBar.tsx           # 승격 조건 진행률
│   │   ├── FeedbackForm.tsx          # Human-in-the-Loop 피드백
│   │   ├── InsightsPanel.tsx         # AI 인사이트 패널
│   │   └── StageProgress.tsx         # 단계 진행 상태
│   ├── lib/
│   │   └── data.ts                   # 데이터 및 평가 로직
│   └── types/
│       └── index.ts                  # TypeScript 타입 정의
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

---

## 컴포넌트 가이드

### AgentCard

개별 에이전트의 상태를 표시하는 카드 컴포넌트입니다.

```tsx
import { AgentCard } from '@/components/AgentCard';

<AgentCard
  agent="issue_analysis"
  result={{
    agent: 'issue_analysis',
    status: 'completed',  // 'pending' | 'running' | 'completed' | 'error'
    durationMs: 2500
  }}
  onViewDetails={() => setSelectedAgent('issue_analysis')}
/>
```

**Props:**
| Prop | Type | 설명 |
|------|------|------|
| `agent` | `AgentType` | 에이전트 타입 |
| `result` | `AgentResult` | 에이전트 실행 결과 |
| `onViewDetails` | `() => void` | 상세 보기 클릭 핸들러 |

---

### AgentPipeline

전체 에이전트 파이프라인과 Human-in-the-Loop 리뷰 UI를 포함합니다.

```tsx
import { AgentPipeline } from '@/components/AgentPipeline';

<AgentPipeline
  pipeline={pipelineState}
  onFeedbackSubmit={(agent, approved, comment) => {
    // 피드백 처리
  }}
/>
```

**Props:**
| Prop | Type | 설명 |
|------|------|------|
| `pipeline` | `IssuePipelineState` | 파이프라인 상태 |
| `onFeedbackSubmit` | `(agent, approved, comment) => void` | 피드백 제출 핸들러 |

**Features:**
- 전체 진행률 프로그레스 바
- 5개 에이전트 카드 그리드
- Human Review 섹션 (awaiting_feedback 상태일 때)
- 피드백 요약 표시

---

### AgentOutputModal

에이전트 출력을 상세히 보여주는 모달입니다.

```tsx
import { AgentOutputModal } from '@/components/AgentOutputModal';

<AgentOutputModal
  agent="issue_analysis"
  result={agentResult}
  onClose={() => setSelectedAgent(null)}
/>
```

각 에이전트 타입별로 커스텀 뷰를 제공합니다:
- `IssueAnalysisView` - 이슈 분석 결과
- `AssignmentView` - 담당자 추천 결과
- `ResponseView` - 응답 생성 결과
- `DocGapView` - 문서 갭 분석 결과
- `PromotionView` - 승격 평가 결과

---

### FeedbackForm

Human-in-the-Loop 피드백 양식입니다.

```tsx
import { FeedbackForm } from '@/components/FeedbackForm';

<FeedbackForm
  agent="issue_analysis"
  result={agentResult}
  onSubmit={(approved, comment) => {
    // approved: boolean, comment: string
  }}
  onClose={() => setFeedbackAgent(null)}
/>
```

**Features:**
- 에이전트 출력 요약 표시
- 승인/거절 버튼
- 코멘트 입력 텍스트 영역

---

### ContributorCard

기여자 정보와 승격 평가 결과를 표시합니다.

```tsx
import { ContributorCard } from '@/components/ContributorCard';

<ContributorCard trace={promotionTrace} />
```

**Sections:**
1. Header - 기여자 정보, 승격 후보 배지
2. Metrics - PRs, Reviews, Activity Score
3. Stage Progress - 현재/제안 단계 시각화
4. Evaluation Result - 신뢰도, 추천 사항
5. Evidence Bar - 승격 조건 진행률
6. AI Insights - 기여 인사이트
7. Decision Trace - 의사결정 과정

---

### DecisionTrace

에이전트의 의사결정 과정을 시각화합니다.

```tsx
import { DecisionTrace } from '@/components/DecisionTrace';

<DecisionTrace
  steps={decisionSteps}
  modelUsed="rule-based"
  durationMs={150}
/>
```

각 스텝을 타임라인 형태로 표시하며, 입력/출력/추론 과정을 보여줍니다.

---

### InsightsPanel

AI가 생성한 기여 인사이트를 표시합니다.

```tsx
import { InsightsPanel } from '@/components/InsightsPanel';

<InsightsPanel insights={contributionInsights} />
```

**Insight Types:**
| Type | 색상 | 설명 |
|------|------|------|
| `strength` | 초록 | 강점 |
| `achievement` | 노랑 | 달성 사항 |
| `trend` | 파랑 | 트렌드 |
| `growth_area` | 주황 | 성장 영역 |
| `recommendation` | 보라 | 추천 사항 |

---

## 타입 정의

### IssuePipelineState

```typescript
interface IssuePipelineState {
  issue: GitHubIssue;
  agents: Record<AgentType, AgentResult>;
  overallProgress: number;  // 0-100
  status: 'idle' | 'running' | 'awaiting_feedback' | 'completed';
  feedbacks: HumanFeedback[];
  startTime?: string;
  endTime?: string;
}
```

### AgentType

```typescript
type AgentType =
  | 'issue_analysis'
  | 'assignment'
  | 'response'
  | 'docs_gap'
  | 'promotion';
```

### HumanFeedback

```typescript
interface HumanFeedback {
  agent: AgentType;
  approved: boolean;
  comment: string;
  reviewer: string;
  timestamp: string;
}
```

---

## 상태 관리 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                        Main Page                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [issues] ────────────────────────────────────────────────► │
│     │                                                        │
│     ▼ (클릭)                                                 │
│  [selectedIssue] ──────────────────────────────────────────► │
│     │                                                        │
│     ▼ (startPipeline)                                       │
│  [pipeline: IssuePipelineState]                             │
│     │                                                        │
│     ├─► status: 'running'                                   │
│     │     │                                                  │
│     │     ▼ (순차 에이전트 실행)                            │
│     │   agents[i].status = 'running' → 'completed'          │
│     │                                                        │
│     ├─► status: 'awaiting_feedback'                         │
│     │     │                                                  │
│     │     ▼ (Human Review)                                  │
│     │   feedbacks[] 추가                                    │
│     │                                                        │
│     └─► status: 'completed'                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 실행 방법

```bash
cd web

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
# http://localhost:3000

# 프로덕션 빌드
npm run build
npm start
```

---

## 스타일링

Tailwind CSS를 사용하며, 주요 색상 클래스:

```css
/* 에이전트 상태 */
.pending   { @apply bg-gray-50 border-gray-200; }
.running   { @apply bg-blue-50 border-blue-300; }
.completed { @apply bg-green-50 border-green-300; }
.error     { @apply bg-red-50 border-red-300; }

/* 프로그레스 바 */
.progress-bar { @apply h-3 bg-gray-200 rounded-full overflow-hidden; }
.progress-fill { @apply h-full bg-gradient-to-r from-indigo-500 to-purple-500; }

/* 인사이트 타입 */
.insight-strength { @apply bg-green-50 border-green-300; }
.insight-achievement { @apply bg-yellow-50 border-yellow-300; }
.insight-trend { @apply bg-blue-50 border-blue-300; }
.insight-growth { @apply bg-orange-50 border-orange-300; }
.insight-recommendation { @apply bg-purple-50 border-purple-300; }
```

---

## 환경 변수

`web/.env.local` 파일 (선택):

```env
GITHUB_TOKEN=ghp_...   # GitHub API 토큰 (rate limit 증가)
```

---

## 확장 포인트

### 새 에이전트 추가

1. `types/index.ts`에 타입 추가
2. `api/agents/run/route.ts`에 실행 로직 추가
3. `AgentOutputModal.tsx`에 커스텀 뷰 추가

### 새 피드백 타입 추가

1. `types/index.ts`의 `HumanFeedback` 확장
2. `FeedbackForm.tsx` 수정
3. `AgentPipeline.tsx`의 피드백 요약 수정
