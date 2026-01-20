// Types matching Python agent types

export interface Contributor {
  login: string;
  areas: string[];
  recent_activity_score: number;
  merged_prs: number;
  reviews: number;
  first_contribution_date?: string;
  last_contribution_date?: string;
}

export interface PromotionEvidence {
  criterion: string;
  status: 'met' | 'not_met' | 'exceeds' | 'below' | 'aligned' | 'moderate' | 'strong' | 'positive' | 'low' | 'broad';
  detail: string;
}

export interface PromotionOutput {
  is_candidate: boolean;
  current_stage: string;
  suggested_stage: string;
  confidence: number;
  evidence: PromotionEvidence[];
  recommendation: string;
}

// Decision trace for observability
export interface DecisionStep {
  step_number: number;
  step_name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  reasoning: string;
  timestamp: string;
}

// Contribution insight for richer context
export interface ContributionInsight {
  type: 'strength' | 'growth_area' | 'achievement' | 'trend' | 'recommendation';
  icon: string;
  title: string;
  description: string;
}

export interface PromotionTrace {
  contributor: Contributor;
  evaluation: PromotionOutput;
  decision_steps: DecisionStep[];
  insights: ContributionInsight[];
  total_duration_ms: number;
  model_used: string;
}

// Stage definitions
export const STAGES = {
  NEW: { order: 0, label: 'New', color: 'gray', minPRs: 0 },
  FIRST_TIMER: { order: 1, label: 'First Timer', color: 'blue', minPRs: 1 },
  REGULAR: { order: 2, label: 'Regular', color: 'green', minPRs: 2 },
  CORE: { order: 3, label: 'Core', color: 'purple', minPRs: 8 },
  MAINTAINER: { order: 4, label: 'Maintainer', color: 'orange', minPRs: 20 },
} as const;

export type StageName = keyof typeof STAGES;

// Criteria thresholds for visualization
export const CRITERIA_THRESHOLDS = {
  recent_activity: { threshold: 2.5, label: 'Recent Activity Score' },
  merged_prs: { threshold: 2, label: 'Merged PRs' },
  reviews: { threshold: 3, label: 'Code Reviews' },
} as const;

// ============================================
// Agent Pipeline Types
// ============================================

// GitHub Issue from Prism repo
export interface GitHubIssue {
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

// Agent execution status
export type AgentStatus = 'pending' | 'running' | 'completed' | 'error';

// Agent types
export type AgentType = 'issue_analysis' | 'assignment' | 'response' | 'docs_gap' | 'promotion';

// Issue Analysis Output
export interface IssueAnalysisOutput {
  issue_type: 'bug' | 'feature' | 'question' | 'documentation' | 'other';
  priority: 'critical' | 'high' | 'medium' | 'low';
  required_skills: string[];
  keywords: string[];
  summary: string;
  needs_more_info: boolean;
  suggested_action: 'direct_answer' | 'request_info' | 'link_docs' | 'escalate';
}

// Assignment Output
export interface AssignmentReason {
  factor: string;
  explanation: string;
  score: number;
}

export interface AssignmentOutput {
  recommended_assignee: string;
  confidence: number;
  reasons: AssignmentReason[];
  context_for_assignee: string;
  alternative_assignees: string[];
}

// Response Output
export interface ResponseOutput {
  strategy: 'direct_answer' | 'request_info' | 'link_docs' | 'escalate';
  response_text: string;
  confidence: number;
  references: string[];
  follow_up_needed: boolean;
}

// Doc Gap Output
export interface DocGapOutput {
  has_gap: boolean;
  gap_topic: string;
  affected_issues: number[];
  suggested_doc_path: string;
  suggested_outline: string[];
  priority: 'critical' | 'high' | 'medium' | 'low';
}

// Agent execution result
export interface AgentResult {
  agent: AgentType;
  status: AgentStatus;
  startTime?: string;
  endTime?: string;
  durationMs?: number;
  output?: IssueAnalysisOutput | AssignmentOutput | ResponseOutput | DocGapOutput | PromotionOutput;
  error?: string;
  decisionTrace?: DecisionStep[];
}

// Human feedback
export interface HumanFeedback {
  agent: AgentType;
  approved: boolean;
  comment: string;
  reviewer: string;
  timestamp: string;
}

// Pipeline state for a single issue
export interface IssuePipelineState {
  issue: GitHubIssue;
  agents: Record<AgentType, AgentResult>;
  overallProgress: number; // 0-100
  status: 'idle' | 'running' | 'awaiting_feedback' | 'completed';
  feedbacks: HumanFeedback[];
  courtResults: Partial<Record<AgentType, CourtResult>>;
  courtRunning: Partial<Record<AgentType, boolean>>;
  startTime?: string;
  endTime?: string;
}

// Agent definitions for display
export const AGENTS: Record<AgentType, { name: string; icon: string; description: string }> = {
  issue_analysis: {
    name: 'Issue Analysis',
    icon: '🔍',
    description: 'Analyze issue type, priority, and required skills',
  },
  assignment: {
    name: 'Assignment',
    icon: '👤',
    description: 'Recommend best contributor for the issue',
  },
  response: {
    name: 'Response',
    icon: '💬',
    description: 'Generate appropriate response strategy',
  },
  docs_gap: {
    name: 'Docs Gap',
    icon: '📚',
    description: 'Detect documentation gaps',
  },
  promotion: {
    name: 'Promotion',
    icon: '🚀',
    description: 'Evaluate contributor promotion candidates',
  },
};

// ============================================
// Phase 3: Retrospective Court Types
// ============================================

// Court stage output (prosecutor, defense, jury, judge)
export interface CourtStageOutput {
  stage: string;
  content: string;
  reasoning: string;
}

// Prompt update proposal from judge
export interface PromptUpdateProposal {
  role: string;
  from_version: number | null;
  proposal: string;
  reason: string;
  status: 'proposed' | 'approved' | 'rejected' | 'applied';
}

// Lesson learned from court
export interface CourtLesson {
  role: string;
  polarity: 'do' | 'do_not';
  title: string;
  content: string;
}

// Full court result for an agent
export interface CourtResult {
  agent: AgentType;
  case_id: string;
  court_run_id: string;
  status: 'running' | 'completed' | 'error';
  stages: {
    prosecutor: CourtStageOutput;
    defense: CourtStageOutput;
    jury: CourtStageOutput;
    judge: CourtStageOutput;
  };
  lessons: CourtLesson[];
  prompt_updates: PromptUpdateProposal[];
}

// Court stage status for streaming
export interface CourtStageStatus {
  prosecutor: 'pending' | 'running' | 'completed';
  defense: 'pending' | 'running' | 'completed';
  jury: 'pending' | 'running' | 'completed';
  judge: 'pending' | 'running' | 'completed';
}

// Court stage definitions for display
export const COURT_STAGES: Record<string, { name: string; icon: string; role: string }> = {
  prosecutor: {
    name: 'Prosecutor',
    icon: '⚖️',
    role: 'Criticizes agent output and identifies issues',
  },
  defense: {
    name: 'Defense',
    icon: '🛡️',
    role: 'Defends agent output and highlights strengths',
  },
  jury: {
    name: 'Jury',
    icon: '👥',
    role: 'Observes and provides neutral assessment',
  },
  judge: {
    name: 'Judge',
    icon: '👨‍⚖️',
    role: 'Delivers final verdict and recommendations',
  },
};
