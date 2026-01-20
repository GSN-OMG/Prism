from __future__ import annotations

import json

from devrel.llm.client import JsonSchema, LlmClient
from devrel.llm.model_selector import LlmTask

from .types import (
    Issue,
    IssueAnalysisOutput,
    ResponseOutput,
    ResponseStrategy,
    response_output_from_dict,
)


def draft_response(issue: Issue, analysis: IssueAnalysisOutput) -> ResponseOutput:
    if analysis.needs_more_info:
        body = (
            "Thanks for the report — to help us reproduce and confirm the fix, could you provide:\n"
            "- Steps to reproduce\n"
            "- Expected vs actual behavior\n"
            "- Environment/version\n"
            "- Relevant logs/stack traces\n"
        )
        return ResponseOutput(
            strategy=ResponseStrategy.REQUEST_INFO,
            response_text=body,
            confidence=0.6,
            references=(),
            follow_up_needed=True,
        )

    body = (
        "Thanks for reaching out. Here are a few next steps to unblock:\n"
        "- Confirm your environment/version\n"
        "- Share logs or errors\n"
        "- Provide a minimal reproduction if possible\n"
    )
    return ResponseOutput(
        strategy=analysis.suggested_action,
        response_text=body,
        confidence=0.5,
        references=(),
        follow_up_needed=False,
    )


def draft_response_llm(
    llm: LlmClient,
    *,
    issue: Issue,
    analysis: IssueAnalysisOutput,
    references: list[str] | None = None,
) -> ResponseOutput:
    schema = JsonSchema(
        name="response_output",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strategy": {"type": "string", "enum": [s.value for s in ResponseStrategy]},
                "response_text": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "references": {"type": "array", "items": {"type": "string"}},
                "follow_up_needed": {"type": "boolean"},
            },
            "required": ["strategy", "response_text", "confidence", "references", "follow_up_needed"],
        },
    )

    system = (
        "You are a DevRel agent responding on GitHub issues.\n"
        "Be accurate, concise, and avoid hallucinating versions/links.\n"
        "If needs_more_info=true, ask for concrete reproduction/environment/logs.\n"
        "Keep response_text short (<= 180 words)."
    )
    payload = {
        "issue": {"number": issue.number, "title": issue.title, "body": issue.body, "labels": list(issue.labels)},
        "analysis": {
            "issue_type": analysis.issue_type.value,
            "priority": analysis.priority.value,
            "required_skills": list(analysis.required_skills),
            "keywords": list(analysis.keywords),
            "summary": analysis.summary,
            "needs_more_info": analysis.needs_more_info,
            "suggested_action": analysis.suggested_action.value,
        },
        "references": references or [],
    }
    user = f"Input:\n{json.dumps(payload, ensure_ascii=False)}"
    data = llm.generate_json(
        task=LlmTask.RESPONSE,
        system=system,
        user=user,
        json_schema=schema,
        max_output_tokens=1200,
    )
    return response_output_from_dict(data)
