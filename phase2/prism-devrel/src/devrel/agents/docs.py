from __future__ import annotations

import json
from dataclasses import dataclass

from devrel.llm.client import JsonSchema, LlmClient
from devrel.llm.model_selector import LlmTask

from .types import DocGapOutput, Issue, Priority
from .types import doc_gap_output_from_dict


@dataclass(frozen=True, slots=True)
class DocGapCandidate:
    topic: str
    evidence_issue_numbers: tuple[int, ...]
    rationale: str


def detect_doc_gaps(issues: list[Issue]) -> list[DocGapCandidate]:
    candidates: dict[str, list[int]] = {}
    for issue in issues:
        labels = {label.lower() for label in issue.labels}
        title_lower = issue.title.lower()
        body_lower = issue.body.lower()

        key: str | None = None
        if "redis" in title_lower or "redis" in body_lower:
            key = "redis"
        elif "logging" in title_lower or "debug" in title_lower or "logging" in body_lower:
            key = "logging"
        elif "documentation" in labels or "docs" in title_lower:
            key = "documentation"

        if key is None:
            continue
        candidates.setdefault(key, []).append(issue.number)

    results: list[DocGapCandidate] = []
    for topic, numbers in candidates.items():
        results.append(
            DocGapCandidate(
                topic=topic,
                evidence_issue_numbers=tuple(sorted(set(numbers))),
                rationale="Multiple issues suggest a recurring documentation gap.",
            )
        )
    return results


def to_doc_gap_output(candidate: DocGapCandidate) -> DocGapOutput:
    numbers = ", ".join(f"#{n}" for n in candidate.evidence_issue_numbers)

    topic = candidate.topic
    if topic == "redis":
        doc_path = "docs/cache/redis.md"
        outline = (
            "Overview",
            "Installation",
            "Configuration",
            "Common errors",
            "Example config",
        )
        priority = Priority.HIGH
    elif topic == "logging":
        doc_path = "docs/debugging/logging.md"
        outline = ("Enable debug logging", "Log locations", "Common troubleshooting")
        priority = Priority.MEDIUM
    else:
        doc_path = "docs/README.md"
        outline = ("Problem statement", "How to", "FAQ")
        priority = Priority.MEDIUM

    return DocGapOutput(
        has_gap=True,
        gap_topic=topic,
        affected_issues=candidate.evidence_issue_numbers,
        suggested_doc_path=doc_path,
        suggested_outline=outline,
        priority=priority,
    )


def summarize_doc_gap(candidate: DocGapCandidate) -> str:
    numbers = ", ".join(f"#{n}" for n in candidate.evidence_issue_numbers)
    return f"Topic={candidate.topic}, evidence={numbers}, rationale={candidate.rationale}"


def detect_doc_gaps_llm(llm: LlmClient, issues: list[Issue]) -> DocGapOutput:
    schema = JsonSchema(
        name="doc_gap_output",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "has_gap": {"type": "boolean"},
                "gap_topic": {"type": "string"},
                "affected_issues": {"type": "array", "items": {"type": "integer"}},
                "suggested_doc_path": {"type": "string"},
                "suggested_outline": {"type": "array", "items": {"type": "string"}},
                "priority": {"type": "string", "enum": [p.value for p in Priority]},
            },
            "required": [
                "has_gap",
                "gap_topic",
                "affected_issues",
                "suggested_doc_path",
                "suggested_outline",
                "priority",
            ],
        },
    )

    system = (
        "You are a DevRel agent that detects documentation gaps from GitHub issues.\n"
        "Return only JSON. Do not hallucinate issue numbers not provided."
    )
    payload = [
        {"number": i.number, "title": i.title, "body": i.body, "labels": list(i.labels)} for i in issues
    ]
    user = f"Issues:\n{json.dumps(payload, ensure_ascii=False)}"
    data = llm.generate_json(task=LlmTask.DOCS, system=system, user=user, json_schema=schema)
    return doc_gap_output_from_dict(data)
