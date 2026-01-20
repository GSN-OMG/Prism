from __future__ import annotations

import json
from dataclasses import dataclass

from devrel.llm.client import JsonSchema, LlmClient
from devrel.llm.model_selector import LlmTask

from .types import (
    DocGapOutput,
    EnhancedDocGapOutput,
    ExternalDocReference,
    Issue,
    Priority,
    doc_gap_output_from_dict,
)


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


def detect_doc_gaps_with_tavily(
    llm: LlmClient,
    issues: list[Issue],
    repo_name: str,
    tavily_api_key: str | None = None,
) -> EnhancedDocGapOutput:
    """Detect documentation gaps with external repo comparison via Tavily.

    Args:
        llm: LLM client
        issues: List of issues to analyze
        repo_name: Target repository name (e.g., "openai/openai-agents-python")
        tavily_api_key: Tavily API key (or set TAVILY_API_KEY env var)
    """
    from devrel.search.tavily_client import TavilyClient

    # 1. Basic doc gap analysis
    base_gap = detect_doc_gaps_llm(llm, issues)

    # 2. Search for similar repos and best practices
    tavily = TavilyClient(api_key=tavily_api_key)

    # Search for similar repos with good documentation
    similar_insight = tavily.search_similar_repos(
        repo_name=repo_name,
        topic=f"{base_gap.gap_topic} documentation",
    )

    # Search for documentation best practices
    best_practices_insight = tavily.search_docs_best_practices(
        topic=base_gap.gap_topic,
        repo_type="python agent framework",
    )

    # 3. Extract external doc references
    external_refs = []
    for result in similar_insight.results[:5]:
        if "github.com" in result.url:
            parts = result.url.replace("https://github.com/", "").split("/")
            repo = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else ""
            doc_path = "/".join(parts[2:]) if len(parts) > 2 else ""

            external_refs.append(
                ExternalDocReference(
                    repo=repo,
                    doc_path=doc_path,
                    url=result.url,
                    description=result.content[:200] if result.content else "",
                    relevance=result.score,
                )
            )

    return EnhancedDocGapOutput(
        gap_analysis=base_gap,
        external_references=tuple(external_refs),
        similar_repos=similar_insight.related_repos,
        best_practices=best_practices_insight.answer,
        tavily_answer=similar_insight.answer,
    )
