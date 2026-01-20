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


def issue_analysis_from_dict(data: dict[str, object]) -> IssueAnalysisOutput:
    return IssueAnalysisOutput(
        issue_type=IssueType(str(data["issue_type"])),
        priority=Priority(str(data["priority"])),
        required_skills=tuple(data.get("required_skills", []) or []),  # type: ignore[arg-type]
        keywords=tuple(data.get("keywords", []) or []),  # type: ignore[arg-type]
        summary=str(data.get("summary", "")),
        needs_more_info=bool(data.get("needs_more_info", False)),
        suggested_action=ResponseStrategy(str(data["suggested_action"])),
    )


def assignment_output_from_dict(data: dict[str, object]) -> AssignmentOutput:
    reasons_raw = data.get("reasons", []) or []
    reasons: list[AssignmentReason] = []
    for r in reasons_raw:  # type: ignore[assignment]
        rr = r  # type: ignore[assignment]
        reasons.append(
            AssignmentReason(
                factor=str(rr["factor"]),
                explanation=str(rr["explanation"]),
                score=float(rr["score"]),
            )
        )
    return AssignmentOutput(
        recommended_assignee=str(data.get("recommended_assignee", "")),
        confidence=float(data.get("confidence", 0.0)),
        reasons=tuple(reasons),
        context_for_assignee=str(data.get("context_for_assignee", "")),
        alternative_assignees=tuple(data.get("alternative_assignees", []) or []),  # type: ignore[arg-type]
    )


def response_output_from_dict(data: dict[str, object]) -> ResponseOutput:
    return ResponseOutput(
        strategy=ResponseStrategy(str(data["strategy"])),
        response_text=str(data.get("response_text", "")),
        confidence=float(data.get("confidence", 0.0)),
        references=tuple(data.get("references", []) or []),  # type: ignore[arg-type]
        follow_up_needed=bool(data.get("follow_up_needed", False)),
    )


def doc_gap_output_from_dict(data: dict[str, object]) -> DocGapOutput:
    return DocGapOutput(
        has_gap=bool(data.get("has_gap", False)),
        gap_topic=str(data.get("gap_topic", "")),
        affected_issues=tuple(data.get("affected_issues", []) or []),  # type: ignore[arg-type]
        suggested_doc_path=str(data.get("suggested_doc_path", "")),
        suggested_outline=tuple(data.get("suggested_outline", []) or []),  # type: ignore[arg-type]
        priority=Priority(str(data["priority"])),
    )


def promotion_output_from_dict(data: dict[str, object]) -> PromotionOutput:
    evidence_raw = data.get("evidence", []) or []
    evidence: list[PromotionEvidence] = []
    for e in evidence_raw:  # type: ignore[assignment]
        ee = e  # type: ignore[assignment]
        evidence.append(
            PromotionEvidence(
                criterion=str(ee["criterion"]),
                status=str(ee["status"]),
                detail=str(ee["detail"]),
            )
        )
    return PromotionOutput(
        is_candidate=bool(data.get("is_candidate", False)),
        current_stage=str(data.get("current_stage", "")),
        suggested_stage=str(data.get("suggested_stage", "")),
        confidence=float(data.get("confidence", 0.0)),
        evidence=tuple(evidence),
        recommendation=str(data.get("recommendation", "")),
    )
