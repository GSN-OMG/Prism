from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .models import Case, CaseEvent, Lesson


@dataclass(frozen=True, slots=True)
class CourtRun:
    id: str
    case_id: str
    model: str
    started_at: datetime
    status: str = "running"
    ended_at: datetime | None = None
    artifacts: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class JudgementRecord:
    id: str
    case_id: str
    court_run_id: str
    decision: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LessonRecord:
    id: str
    case_id: str
    lesson: Lesson
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PromptUpdateRecord:
    id: str
    case_id: str
    role: str
    proposal: str
    reason: str
    status: str
    created_at: datetime
    agent_id: str | None = None
    from_version: str | None = None
    evidence_event_ids: tuple[str, ...] = ()


class Storage(Protocol):
    def create_case(
        self,
        *,
        source: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        feedback: dict[str, Any] | None = None,
        redaction_policy_version: str | None = None,
    ) -> str: ...

    def get_case(self, case_id: str) -> Case: ...

    def list_case_events(self, case_id: str) -> list[CaseEvent]: ...

    def append_case_events(self, case_id: str, events: list[CaseEvent]) -> None: ...

    def create_court_run(
        self, case_id: str, model: str, started_at: datetime
    ) -> str: ...

    def finish_court_run(
        self, court_run_id: str, *, status: str, artifacts_redacted: dict[str, Any]
    ) -> None: ...

    def store_judgement(
        self, *, case_id: str, court_run_id: str, decision_json: dict[str, Any]
    ) -> str: ...

    def store_lessons(self, *, case_id: str, lessons: list[Lesson]) -> list[str]: ...

    def store_prompt_update(
        self,
        *,
        case_id: str,
        agent_id: str | None,
        role: str,
        from_version: str | None,
        proposal: str,
        reason: str,
        evidence_event_ids: tuple[str, ...],
        status: str = "proposed",
    ) -> str: ...

    def search_lessons(
        self, *, role: str, query: str, k: int = 5
    ) -> list[LessonRecord]: ...


class InMemoryStorage:
    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}
        self._events: dict[str, list[CaseEvent]] = {}
        self._court_runs: dict[str, CourtRun] = {}
        self._judgements: dict[str, JudgementRecord] = {}
        self._lessons: dict[str, LessonRecord] = {}
        self._prompt_updates: dict[str, PromptUpdateRecord] = {}

    @property
    def cases(self) -> dict[str, Case]:
        return self._cases

    @property
    def events(self) -> dict[str, list[CaseEvent]]:
        return self._events

    @property
    def court_runs(self) -> dict[str, CourtRun]:
        return self._court_runs

    @property
    def judgements(self) -> dict[str, JudgementRecord]:
        return self._judgements

    @property
    def lessons(self) -> dict[str, LessonRecord]:
        return self._lessons

    @property
    def prompt_updates(self) -> dict[str, PromptUpdateRecord]:
        return self._prompt_updates

    def create_case(
        self,
        *,
        source: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        feedback: dict[str, Any] | None = None,
        redaction_policy_version: str | None = None,
    ) -> str:
        case_id = str(uuid.uuid4())
        self._cases[case_id] = Case(
            id=case_id,
            source=source or {},
            metadata=metadata or {},
            result=result or {},
            feedback=feedback or {},
            created_at=datetime.now(timezone.utc),
            redaction_policy_version=redaction_policy_version,
        )
        self._events[case_id] = []
        return case_id

    def get_case(self, case_id: str) -> Case:
        return self._cases[case_id]

    def list_case_events(self, case_id: str) -> list[CaseEvent]:
        return list(self._events.get(case_id, []))

    def append_case_events(self, case_id: str, events: list[CaseEvent]) -> None:
        self._events.setdefault(case_id, []).extend(events)

    def create_court_run(self, case_id: str, model: str, started_at: datetime) -> str:
        court_run_id = str(uuid.uuid4())
        self._court_runs[court_run_id] = CourtRun(
            id=court_run_id,
            case_id=case_id,
            model=model,
            started_at=started_at,
            status="running",
        )
        return court_run_id

    def finish_court_run(
        self, court_run_id: str, *, status: str, artifacts_redacted: dict[str, Any]
    ) -> None:
        run = self._court_runs[court_run_id]
        self._court_runs[court_run_id] = CourtRun(
            id=run.id,
            case_id=run.case_id,
            model=run.model,
            started_at=run.started_at,
            status=status,
            ended_at=datetime.now(timezone.utc),
            artifacts=artifacts_redacted,
        )

    def store_judgement(
        self, *, case_id: str, court_run_id: str, decision_json: dict[str, Any]
    ) -> str:
        judgement_id = str(uuid.uuid4())
        self._judgements[judgement_id] = JudgementRecord(
            id=judgement_id,
            case_id=case_id,
            court_run_id=court_run_id,
            decision=decision_json,
            created_at=datetime.now(timezone.utc),
        )
        return judgement_id

    def store_lessons(self, *, case_id: str, lessons: list[Lesson]) -> list[str]:
        ids: list[str] = []
        for lesson in lessons:
            lesson_id = str(uuid.uuid4())
            self._lessons[lesson_id] = LessonRecord(
                id=lesson_id,
                case_id=case_id,
                lesson=lesson,
                created_at=datetime.now(timezone.utc),
            )
            ids.append(lesson_id)
        return ids

    def store_prompt_update(
        self,
        *,
        case_id: str,
        agent_id: str | None,
        role: str,
        from_version: str | None,
        proposal: str,
        reason: str,
        evidence_event_ids: tuple[str, ...],
        status: str = "proposed",
    ) -> str:
        update_id = str(uuid.uuid4())
        self._prompt_updates[update_id] = PromptUpdateRecord(
            id=update_id,
            case_id=case_id,
            agent_id=agent_id,
            role=role,
            from_version=from_version,
            proposal=proposal,
            reason=reason,
            status=status,
            created_at=datetime.now(timezone.utc),
            evidence_event_ids=evidence_event_ids,
        )
        return update_id

    def search_lessons(
        self, *, role: str, query: str, k: int = 5
    ) -> list[LessonRecord]:
        # MVP: naive role filter, no embeddings.
        matches = [r for r in self._lessons.values() if r.lesson.role == role]
        return matches[:k]
