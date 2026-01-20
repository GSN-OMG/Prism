from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypedDict

ActorType = Literal["human", "ai", "tool", "system"]
LessonPolarity = Literal["do", "dont"]


def _expect_dict(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return value


def _expect_list(value: Any, *, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{where} must be an array")
    return value


def _expect_str(value: Any, *, where: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{where} must be a string")
    return value


def _expect_float(value: Any, *, where: str) -> float:
    if not isinstance(value, (int, float)):
        raise TypeError(f"{where} must be a number")
    return float(value)


def _expect_optional_str(value: Any, *, where: str) -> str | None:
    if value is None:
        return None
    return _expect_str(value, where=where)


def _expect_optional_float(value: Any, *, where: str) -> float | None:
    if value is None:
        return None
    return _expect_float(value, where=where)


def _expect_str_list(value: Any, *, where: str) -> list[str]:
    arr = _expect_list(value, where=where)
    out: list[str] = []
    for idx, item in enumerate(arr):
        out.append(_expect_str(item, where=f"{where}[{idx}]"))
    return out


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    source: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    feedback: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    redaction_policy_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "source": self.source,
            "metadata": self.metadata,
            "result": self.result,
            "feedback": self.feedback,
        }
        if self.created_at is not None:
            out["created_at"] = self.created_at.isoformat()
        if self.redaction_policy_version is not None:
            out["redaction_policy_version"] = self.redaction_policy_version
        return out


@dataclass(frozen=True, slots=True)
class CaseEvent:
    id: str
    actor_type: ActorType
    event_type: str
    content: str
    ts: datetime | None = None
    seq: int | None = None
    actor_id: str | None = None
    role: str | None = None
    court_run_id: str | None = None
    stage: str | None = None
    usage: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "actor_type": self.actor_type,
            "event_type": self.event_type,
            "content": self.content,
        }
        if self.ts is not None:
            out["ts"] = self.ts.isoformat()
        if self.seq is not None:
            out["seq"] = self.seq
        if self.actor_id is not None:
            out["actor_id"] = self.actor_id
        if self.role is not None:
            out["role"] = self.role
        if self.court_run_id is not None:
            out["court_run_id"] = self.court_run_id
        if self.stage is not None:
            out["stage"] = self.stage
        if self.usage is not None:
            out["usage"] = self.usage
        if self.meta is not None:
            out["meta"] = self.meta
        return out


@dataclass(frozen=True, slots=True)
class Lesson:
    role: str
    polarity: LessonPolarity
    title: str
    content: str
    rationale: str | None
    confidence: float | None
    tags: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: Any, *, where: str = "lesson") -> Lesson:
        obj = _expect_dict(raw, where=where)
        role = _expect_str(obj.get("role"), where=f"{where}.role")
        polarity = _expect_str(obj.get("polarity"), where=f"{where}.polarity")
        if polarity not in ("do", "dont"):
            raise TypeError(f"{where}.polarity must be 'do' or 'dont'")
        return cls(
            role=role,
            polarity=polarity,  # type: ignore[arg-type]
            title=_expect_str(obj.get("title"), where=f"{where}.title"),
            content=_expect_str(obj.get("content"), where=f"{where}.content"),
            rationale=_expect_optional_str(
                obj.get("rationale"), where=f"{where}.rationale"
            ),
            confidence=_expect_optional_float(
                obj.get("confidence"), where=f"{where}.confidence"
            ),
            tags=tuple(_expect_str_list(obj.get("tags", []), where=f"{where}.tags")),
            evidence_event_ids=tuple(
                _expect_str_list(
                    obj.get("evidence_event_ids", []),
                    where=f"{where}.evidence_event_ids",
                )
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "polarity": self.polarity,
            "title": self.title,
            "content": self.content,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "tags": list(self.tags),
            "evidence_event_ids": list(self.evidence_event_ids),
        }


@dataclass(frozen=True, slots=True)
class DeferredLesson:
    lesson: Lesson
    reason: str

    @classmethod
    def from_dict(cls, raw: Any, *, where: str = "deferred_lesson") -> DeferredLesson:
        obj = _expect_dict(raw, where=where)
        return cls(
            lesson=Lesson.from_dict(obj.get("lesson"), where=f"{where}.lesson"),
            reason=_expect_str(obj.get("reason"), where=f"{where}.reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"lesson": self.lesson.to_dict(), "reason": self.reason}


@dataclass(frozen=True, slots=True)
class PromptUpdateProposal:
    role: str
    proposal: str
    reason: str
    evidence_event_ids: tuple[str, ...]
    agent_id: str | None = None
    from_version: str | None = None

    @classmethod
    def from_dict(
        cls, raw: Any, *, where: str = "prompt_update_proposal"
    ) -> PromptUpdateProposal:
        obj = _expect_dict(raw, where=where)
        return cls(
            role=_expect_str(obj.get("role"), where=f"{where}.role"),
            agent_id=_expect_optional_str(
                obj.get("agent_id"), where=f"{where}.agent_id"
            ),
            from_version=_expect_optional_str(
                obj.get("from_version"), where=f"{where}.from_version"
            ),
            proposal=_expect_str(obj.get("proposal"), where=f"{where}.proposal"),
            reason=_expect_str(obj.get("reason"), where=f"{where}.reason"),
            evidence_event_ids=tuple(
                _expect_str_list(
                    obj.get("evidence_event_ids", []),
                    where=f"{where}.evidence_event_ids",
                )
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "role": self.role,
            "proposal": self.proposal,
            "reason": self.reason,
            "evidence_event_ids": list(self.evidence_event_ids),
        }
        if self.agent_id is not None:
            out["agent_id"] = self.agent_id
        if self.from_version is not None:
            out["from_version"] = self.from_version
        return out


@dataclass(frozen=True, slots=True)
class ImprovementSuggestion:
    title: str
    content: str
    rationale: str | None
    evidence_event_ids: tuple[str, ...]

    @classmethod
    def from_dict(
        cls, raw: Any, *, where: str = "improvement"
    ) -> ImprovementSuggestion:
        obj = _expect_dict(raw, where=where)
        return cls(
            title=_expect_str(obj.get("title"), where=f"{where}.title"),
            content=_expect_str(obj.get("content"), where=f"{where}.content"),
            rationale=_expect_optional_str(
                obj.get("rationale"), where=f"{where}.rationale"
            ),
            evidence_event_ids=tuple(
                _expect_str_list(
                    obj.get("evidence_event_ids", []),
                    where=f"{where}.evidence_event_ids",
                )
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "rationale": self.rationale,
            "evidence_event_ids": list(self.evidence_event_ids),
        }


@dataclass(frozen=True, slots=True)
class ProsecutorOutput:
    criticisms: tuple[str, ...]
    candidate_lessons: tuple[Lesson, ...]

    @classmethod
    def from_dict(cls, raw: Any, *, where: str = "prosecutor") -> ProsecutorOutput:
        obj = _expect_dict(raw, where=where)
        criticisms = tuple(
            _expect_str_list(obj.get("criticisms", []), where=f"{where}.criticisms")
        )
        raw_lessons = _expect_list(
            obj.get("candidate_lessons", []), where=f"{where}.candidate_lessons"
        )
        return cls(
            criticisms=criticisms,
            candidate_lessons=tuple(
                Lesson.from_dict(item, where=f"{where}.candidate_lessons[{idx}]")
                for idx, item in enumerate(raw_lessons)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "criticisms": list(self.criticisms),
            "candidate_lessons": [
                lesson.to_dict() for lesson in self.candidate_lessons
            ],
        }


@dataclass(frozen=True, slots=True)
class DefenseOutput:
    praises: tuple[str, ...]
    candidate_lessons: tuple[Lesson, ...]

    @classmethod
    def from_dict(cls, raw: Any, *, where: str = "defense") -> DefenseOutput:
        obj = _expect_dict(raw, where=where)
        praises = tuple(
            _expect_str_list(obj.get("praises", []), where=f"{where}.praises")
        )
        raw_lessons = _expect_list(
            obj.get("candidate_lessons", []), where=f"{where}.candidate_lessons"
        )
        return cls(
            praises=praises,
            candidate_lessons=tuple(
                Lesson.from_dict(item, where=f"{where}.candidate_lessons[{idx}]")
                for idx, item in enumerate(raw_lessons)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "praises": list(self.praises),
            "candidate_lessons": [
                lesson.to_dict() for lesson in self.candidate_lessons
            ],
        }


@dataclass(frozen=True, slots=True)
class JuryOutput:
    observations: tuple[str, ...]
    risks: tuple[str, ...]
    missing_info: tuple[str, ...]
    candidate_lessons: tuple[Lesson, ...]

    @classmethod
    def from_dict(cls, raw: Any, *, where: str = "jury") -> JuryOutput:
        obj = _expect_dict(raw, where=where)
        observations = tuple(
            _expect_str_list(obj.get("observations", []), where=f"{where}.observations")
        )
        risks = tuple(_expect_str_list(obj.get("risks", []), where=f"{where}.risks"))
        missing_info = tuple(
            _expect_str_list(obj.get("missing_info", []), where=f"{where}.missing_info")
        )
        raw_lessons = _expect_list(
            obj.get("candidate_lessons", []), where=f"{where}.candidate_lessons"
        )
        return cls(
            observations=observations,
            risks=risks,
            missing_info=missing_info,
            candidate_lessons=tuple(
                Lesson.from_dict(item, where=f"{where}.candidate_lessons[{idx}]")
                for idx, item in enumerate(raw_lessons)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observations": list(self.observations),
            "risks": list(self.risks),
            "missing_info": list(self.missing_info),
            "candidate_lessons": [
                lesson.to_dict() for lesson in self.candidate_lessons
            ],
        }


@dataclass(frozen=True, slots=True)
class JudgeOutput:
    selected_lessons: tuple[Lesson, ...]
    deferred_lessons: tuple[DeferredLesson, ...]
    prompt_update_proposals: tuple[PromptUpdateProposal, ...]
    user_improvement_suggestions: tuple[ImprovementSuggestion, ...] = ()
    system_improvement_suggestions: tuple[ImprovementSuggestion, ...] = ()

    @classmethod
    def from_dict(cls, raw: Any, *, where: str = "judge") -> JudgeOutput:
        obj = _expect_dict(raw, where=where)

        raw_selected = _expect_list(
            obj.get("selected_lessons", []), where=f"{where}.selected_lessons"
        )
        raw_deferred = _expect_list(
            obj.get("deferred_lessons", []), where=f"{where}.deferred_lessons"
        )
        raw_proposals = _expect_list(
            obj.get("prompt_update_proposals", []),
            where=f"{where}.prompt_update_proposals",
        )
        raw_user = _expect_list(
            obj.get("user_improvement_suggestions", []),
            where=f"{where}.user_improvement_suggestions",
        )
        raw_system = _expect_list(
            obj.get("system_improvement_suggestions", []),
            where=f"{where}.system_improvement_suggestions",
        )

        return cls(
            selected_lessons=tuple(
                Lesson.from_dict(item, where=f"{where}.selected_lessons[{idx}]")
                for idx, item in enumerate(raw_selected)
            ),
            deferred_lessons=tuple(
                DeferredLesson.from_dict(item, where=f"{where}.deferred_lessons[{idx}]")
                for idx, item in enumerate(raw_deferred)
            ),
            prompt_update_proposals=tuple(
                PromptUpdateProposal.from_dict(
                    item, where=f"{where}.prompt_update_proposals[{idx}]"
                )
                for idx, item in enumerate(raw_proposals)
            ),
            user_improvement_suggestions=tuple(
                ImprovementSuggestion.from_dict(
                    item, where=f"{where}.user_improvement_suggestions[{idx}]"
                )
                for idx, item in enumerate(raw_user)
            ),
            system_improvement_suggestions=tuple(
                ImprovementSuggestion.from_dict(
                    item, where=f"{where}.system_improvement_suggestions[{idx}]"
                )
                for idx, item in enumerate(raw_system)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_lessons": [lesson.to_dict() for lesson in self.selected_lessons],
            "deferred_lessons": [lesson.to_dict() for lesson in self.deferred_lessons],
            "prompt_update_proposals": [
                p.to_dict() for p in self.prompt_update_proposals
            ],
            "user_improvement_suggestions": [
                s.to_dict() for s in self.user_improvement_suggestions
            ],
            "system_improvement_suggestions": [
                s.to_dict() for s in self.system_improvement_suggestions
            ],
        }


class AgentRunResult(TypedDict, total=False):
    output: dict[str, Any]
    usage: dict[str, Any]
    meta: dict[str, Any]


def json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
