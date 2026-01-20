from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str
    labels: tuple[str, ...] = ()


class IssueKind(str, Enum):
    BUG = "bug"
    QUESTION = "question"
    DOCUMENTATION = "documentation"
    FEATURE = "feature"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class IssueAnalysis:
    kind: IssueKind
    summary: str
    missing_info_questions: tuple[str, ...] = ()
    suggested_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Contributor:
    login: str
    areas: tuple[str, ...] = ()
    recent_activity_score: float = 0.0


@dataclass(frozen=True, slots=True)
class AssigneeRecommendation:
    login: str
    score: float
    rationale: str


@dataclass(frozen=True, slots=True)
class AgentOutput:
    title: str
    body: str
    metadata: dict[str, object] | None = None

