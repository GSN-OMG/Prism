from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from devrel.agents.types import Issue, IssueAnalysisOutput


@dataclass(frozen=True, slots=True)
class JudgeResult:
    passed: bool
    score: int
    feedback: str


def _llm_judge_enabled() -> bool:
    if os.getenv("RUN_LLM_JUDGE", "0") not in ("1", "true", "TRUE", "yes", "YES"):
        return False
    return bool(os.getenv("OPENAI_API_KEY"))


def judge_response_text(*, issue: Issue, analysis: IssueAnalysisOutput, response_text: str) -> JudgeResult:
    if not _llm_judge_enabled():
        pytest.skip("LLM judge disabled (set RUN_LLM_JUDGE=1 and OPENAI_API_KEY)")

    from openai import OpenAI

    model = os.getenv("OPENAI_JUDGE_MODEL", "gpt-4.1-mini")
    client = OpenAI()

    schema = {
        "name": "judge_result",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "passed": {"type": "boolean"},
                "score": {"type": "integer", "minimum": 0, "maximum": 10},
                "feedback": {"type": "string"},
            },
            "required": ["passed", "score", "feedback"],
        },
        "strict": True,
    }

    system = (
        "You are a strict evaluator for DevRel agent outputs.\n"
        "Judge the response quality for correctness, clarity, and safety.\n"
        "Fail if the response is vague, hallucinates specifics, or ignores missing info.\n"
        "Return JSON only."
    )
    user = (
        f"Issue title: {issue.title}\n"
        f"Issue body: {issue.body}\n"
        f"Analysis: issue_type={analysis.issue_type.value}, priority={analysis.priority.value}, "
        f"needs_more_info={analysis.needs_more_info}, suggested_action={analysis.suggested_action.value}\n\n"
        f"Response text:\n{response_text}\n\n"
        "Criteria:\n"
        "- If needs_more_info=true, the response must ask for concrete reproduction/environment/logs.\n"
        "- Must not invent stack traces, versions, or links.\n"
        "- Must be actionable and polite.\n"
        "Decide pass/fail and provide brief feedback."
    )

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        text={"format": {"type": "json_schema", "json_schema": schema}},
    )

    raw = resp.output_text
    import json

    data = json.loads(raw)
    return JudgeResult(passed=bool(data["passed"]), score=int(data["score"]), feedback=str(data["feedback"]))

