from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .models import (
    AgentRunResult,
    Case,
    CaseEvent,
    DefenseOutput,
    JudgeOutput,
    JuryOutput,
    ProsecutorOutput,
    json_compact,
)
from .redaction import Redactor
from .storage import Storage


class AgentRunner(Protocol):
    async def run(
        self, *, stage: str, input: dict[str, Any], tools: "CourtTools"
    ) -> AgentRunResult: ...


class CourtTools:
    def __init__(self, *, storage: Storage, redactor: Redactor, case_id: str) -> None:
        self._storage = storage
        self._redactor = redactor
        self._case_id = case_id

    def get_case(self) -> dict[str, Any]:
        return _case_context(self._storage.get_case(self._case_id), self._redactor)

    def list_case_events(self) -> list[dict[str, Any]]:
        return [
            _event_context(e, self._redactor)
            for e in self._storage.list_case_events(self._case_id)
        ]

    def search_lessons(
        self, *, role: str, query: str, k: int = 5
    ) -> list[dict[str, Any]]:
        # NOTE: search implementation lives in the storage module; orchestrator only wires the tool.
        records = self._storage.search_lessons(role=role, query=query, k=k)
        return self._redactor.redact(
            [{"id": r.id, "case_id": r.case_id, **r.lesson.to_dict()} for r in records]
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_event_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class CourtRunSummary:
    case_id: str
    court_run_id: str
    status: str


def _case_context(case: Case, redactor: Redactor) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": case.id,
        "source": redactor.redact(case.source),
        "metadata": redactor.redact(case.metadata),
        "result": redactor.redact(case.result),
        "feedback": redactor.redact(case.feedback),
        "redaction_policy_version": case.redaction_policy_version,
    }
    if case.created_at is not None:
        out["created_at"] = case.created_at.isoformat()
    return out


def _event_context(event: CaseEvent, redactor: Redactor) -> dict[str, Any]:
    out = event.to_dict()
    out["content"] = redactor.redact(out.get("content"))
    if "meta" in out:
        out["meta"] = redactor.redact(out["meta"])
    if "usage" in out:
        out["usage"] = redactor.redact(out["usage"])
    return out


class CourtOrchestrator:
    def __init__(
        self, *, storage: Storage, agent_runner: AgentRunner, redactor: Redactor
    ) -> None:
        self._storage = storage
        self._agent_runner = agent_runner
        self._redactor = redactor

    async def run_case(
        self, *, case_id: str, model: str = "unspecified"
    ) -> CourtRunSummary:
        case = self._storage.get_case(case_id)
        case_events = self._storage.list_case_events(case_id)

        court_run_id = self._storage.create_court_run(case_id, model, _utcnow())
        tools = CourtTools(
            storage=self._storage, redactor=self._redactor, case_id=case_id
        )

        base_context = {
            "case": _case_context(case, self._redactor),
            "events": [_event_context(e, self._redactor) for e in case_events],
        }

        stages = ("prosecutor", "defense", "jury")
        stage_tasks = [
            asyncio.create_task(
                self._run_stage(
                    case_id=case_id,
                    court_run_id=court_run_id,
                    stage=stage,
                    tools=tools,
                    input_payload=base_context,
                )
            )
            for stage in stages
        ]
        stage_results = await asyncio.gather(*stage_tasks)
        stage_outputs: dict[str, dict[str, Any] | None] = {}
        stage_errors: dict[str, str] = {}
        stage_usages: dict[str, dict[str, Any]] = {}
        for stage, result in zip(stages, stage_results, strict=True):
            if result.error is not None:
                stage_errors[stage] = self._redactor.redact(result.error)
                stage_outputs[stage] = None
            else:
                stage_outputs[stage] = result.output
                if result.usage is not None:
                    stage_usages[stage] = result.usage

        judge_input = {
            "case": base_context["case"],
            "events": base_context["events"],
            "stage_outputs": stage_outputs,
            "stage_errors": stage_errors,
        }
        judge_result = await self._run_stage(
            case_id=case_id,
            court_run_id=court_run_id,
            stage="judge",
            tools=tools,
            input_payload=judge_input,
        )

        artifacts: dict[str, Any] = {
            "context": base_context,
            "stages": {
                "prosecutor": stage_outputs["prosecutor"],
                "defense": stage_outputs["defense"],
                "jury": stage_outputs["jury"],
                "judge": judge_result.output,
            },
            "errors": self._redactor.redact(
                {"judge": judge_result.error, **stage_errors}
            ),
            "usage": {"judge": judge_result.usage, **stage_usages},
        }

        status = "completed"
        if stage_errors or judge_result.error is not None:
            status = "completed_with_errors"

        # Persist judge-derived outputs if we have a valid judge JSON result.
        if judge_result.error is None and judge_result.output is not None:
            judge_output = JudgeOutput.from_dict(judge_result.output, where="judge")
            decision_json = self._redactor.redact(judge_output.to_dict())
            self._storage.store_judgement(
                case_id=case_id,
                court_run_id=court_run_id,
                decision_json=decision_json,
            )

            self._storage.store_lessons(
                case_id=case_id, lessons=list(judge_output.selected_lessons)
            )

            for proposal in judge_output.prompt_update_proposals:
                self._storage.store_prompt_update(
                    case_id=case_id,
                    agent_id=proposal.agent_id,
                    role=proposal.role,
                    from_version=proposal.from_version,
                    proposal=proposal.proposal,
                    reason=proposal.reason,
                    evidence_event_ids=proposal.evidence_event_ids,
                    status="proposed",
                )

        self._storage.finish_court_run(
            court_run_id,
            status=status,
            artifacts_redacted=artifacts,
        )

        self._storage.append_case_events(
            case_id,
            [
                CaseEvent(
                    id=_new_event_id(),
                    ts=_utcnow(),
                    actor_type="system",
                    actor_id="court_orchestrator",
                    stage="judge",
                    court_run_id=court_run_id,
                    event_type="artifact",
                    content="Court run finished",
                    meta={"artifacts": artifacts, "status": status},
                )
            ],
        )

        return CourtRunSummary(
            case_id=case_id, court_run_id=court_run_id, status=status
        )

    async def _run_stage(
        self,
        *,
        case_id: str,
        court_run_id: str,
        stage: str,
        tools: CourtTools,
        input_payload: dict[str, Any],
    ) -> "_StageResult":
        call_event = CaseEvent(
            id=_new_event_id(),
            ts=_utcnow(),
            actor_type="system",
            actor_id="court_orchestrator",
            stage=stage,
            court_run_id=court_run_id,
            event_type="model_call",
            content=f"{stage} started",
            meta={
                "stage": stage,
                "input_bytes": len(json_compact(input_payload).encode("utf-8")),
            },
        )
        self._storage.append_case_events(case_id, [self._redacted_event(call_event)])

        try:
            result = await self._agent_runner.run(
                stage=stage, input=input_payload, tools=tools
            )
            output = result.get("output")
            usage = result.get("usage")
            meta = result.get("meta")

            parsed_output = self._parse_stage_output(stage=stage, output=output)
            redacted_output = self._redactor.redact(parsed_output)
            redacted_usage = self._redactor.redact(usage) if usage is not None else None

            result_event = CaseEvent(
                id=_new_event_id(),
                ts=_utcnow(),
                actor_type="system",
                actor_id="court_orchestrator",
                stage=stage,
                court_run_id=court_run_id,
                event_type="model_result",
                content=f"{stage} finished",
                usage=redacted_usage,
                meta=self._redactor.redact(meta) if meta is not None else None,
            )
            artifact_event = CaseEvent(
                id=_new_event_id(),
                ts=_utcnow(),
                actor_type="ai",
                actor_id=stage,
                role=stage,
                stage=stage,
                court_run_id=court_run_id,
                event_type="artifact",
                content=f"{stage} output",
                meta={"output": redacted_output},
            )
            self._storage.append_case_events(
                case_id,
                [
                    self._redacted_event(result_event),
                    self._redacted_event(artifact_event),
                ],
            )

            return _StageResult(
                output=redacted_output, usage=redacted_usage, error=None
            )
        except Exception as exc:  # noqa: BLE001 - boundary: record and continue
            error_event = CaseEvent(
                id=_new_event_id(),
                ts=_utcnow(),
                actor_type="system",
                actor_id="court_orchestrator",
                stage=stage,
                court_run_id=court_run_id,
                event_type="error",
                content=f"{stage} failed",
                meta={"error": str(exc)},
            )
            self._storage.append_case_events(
                case_id, [self._redacted_event(error_event)]
            )
            return _StageResult(output=None, usage=None, error=str(exc))

    def _parse_stage_output(self, *, stage: str, output: Any) -> dict[str, Any]:
        if output is None:
            raise ValueError("Agent output is missing")
        if stage == "prosecutor":
            return ProsecutorOutput.from_dict(output).to_dict()
        if stage == "defense":
            return DefenseOutput.from_dict(output).to_dict()
        if stage == "jury":
            return JuryOutput.from_dict(output).to_dict()
        if stage == "judge":
            return JudgeOutput.from_dict(output).to_dict()
        raise ValueError(f"Unknown stage: {stage}")

    def _redacted_event(self, event: CaseEvent) -> CaseEvent:
        d = event.to_dict()
        return CaseEvent(
            id=d["id"],
            actor_type=d["actor_type"],
            event_type=d["event_type"],
            content=self._redactor.redact(d["content"]),
            ts=datetime.fromisoformat(d["ts"]) if "ts" in d else None,
            seq=d.get("seq"),
            actor_id=d.get("actor_id"),
            role=d.get("role"),
            court_run_id=d.get("court_run_id"),
            stage=d.get("stage"),
            usage=self._redactor.redact(d.get("usage"))
            if d.get("usage") is not None
            else None,
            meta=self._redactor.redact(d.get("meta"))
            if d.get("meta") is not None
            else None,
        )


@dataclass(frozen=True, slots=True)
class _StageResult:
    output: dict[str, Any] | None
    usage: dict[str, Any] | None
    error: str | None
