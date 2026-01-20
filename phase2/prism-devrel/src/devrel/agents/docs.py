from __future__ import annotations

from dataclasses import dataclass

from .types import DocGapOutput, Issue, Priority


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
