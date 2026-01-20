from __future__ import annotations

from dataclasses import dataclass

from .types import AgentOutput, Issue, IssueKind


@dataclass(frozen=True, slots=True)
class DocGapCandidate:
    topic: str
    evidence_issue_numbers: tuple[int, ...]
    rationale: str


def detect_doc_gaps(issues: list[Issue]) -> list[DocGapCandidate]:
    candidates: dict[str, list[int]] = {}
    for issue in issues:
        labels = {label.lower() for label in issue.labels}
        if "documentation" in labels or "docs" in issue.title.lower():
            key = "documentation"
        elif "redis" in issue.title.lower() or "redis" in issue.body.lower():
            key = "redis"
        else:
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


def draft_docs_issue(candidate: DocGapCandidate) -> AgentOutput:
    numbers = ", ".join(f"#{n}" for n in candidate.evidence_issue_numbers)
    body = (
        "We’ve seen repeated questions that indicate a documentation gap.\n\n"
        f"Topic: {candidate.topic}\n"
        f"Evidence: {numbers}\n\n"
        "Proposed action:\n"
        "- Add a short guide and troubleshooting section\n"
        "- Link example configs in `examples/`\n"
    )
    return AgentOutput(title=f"Docs gap: {candidate.topic}", body=body)

