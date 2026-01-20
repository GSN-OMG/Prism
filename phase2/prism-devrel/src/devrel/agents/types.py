from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str
    labels: tuple[str, ...] = ()


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


@dataclass(frozen=True, slots=True)
class IssueAnalysisOutput:
    issue_type: IssueType
    priority: Priority
    required_skills: tuple[str, ...]
    keywords: tuple[str, ...]
    summary: str
    needs_more_info: bool
    suggested_action: ResponseStrategy


@dataclass(frozen=True, slots=True)
class Contributor:
    login: str
    areas: tuple[str, ...] = ()
    recent_activity_score: float = 0.0
    merged_prs: int = 0
    reviews: int = 0
    first_contribution_date: str | None = None
    last_contribution_date: str | None = None


@dataclass(frozen=True, slots=True)
class AssignmentReason:
    factor: str
    explanation: str
    score: float


@dataclass(frozen=True, slots=True)
class AssignmentOutput:
    recommended_assignee: str
    confidence: float
    reasons: tuple[AssignmentReason, ...]
    context_for_assignee: str
    alternative_assignees: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResponseOutput:
    strategy: ResponseStrategy
    response_text: str
    confidence: float
    references: tuple[str, ...]
    follow_up_needed: bool


@dataclass(frozen=True, slots=True)
class DocGapOutput:
    has_gap: bool
    gap_topic: str
    affected_issues: tuple[int, ...]
    suggested_doc_path: str
    suggested_outline: tuple[str, ...]
    priority: Priority


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    criterion: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class PromotionOutput:
    is_candidate: bool
    current_stage: str
    suggested_stage: str
    confidence: float
    evidence: tuple[PromotionEvidence, ...]
    recommendation: str


@dataclass(frozen=True, slots=True)
class AgentOutput:
    title: str
    body: str
    metadata: dict[str, object] | None = None
