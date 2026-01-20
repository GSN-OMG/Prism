from __future__ import annotations

import json
from dataclasses import dataclass

from devrel.llm.client import JsonSchema, LlmClient
from devrel.llm.model_selector import LlmTask

from .types import (
    DocGapOutput,
    DocsComparisonResult,
    EnhancedDocGapOutput,
    ExternalDocReference,
    GitHubEnhancedDocGapOutput,
    Issue,
    Priority,
    RepoDocFile,
    RepoDocsInfo,
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


def detect_doc_gaps_with_github(
    llm: LlmClient,
    issues: list[Issue],
    target_repo: str,
    reference_repos: list[str] | None = None,
    github_token: str | None = None,
) -> GitHubEnhancedDocGapOutput:
    """Detect documentation gaps by comparing with reference repositories via GitHub API.

    Args:
        llm: LLM client
        issues: List of issues to analyze
        target_repo: Target repository name (e.g., "openai/openai-agents-python")
        reference_repos: List of reference repos to compare (auto-detected if None)
        github_token: GitHub token (or set GITHUB_TOKEN env var)
    """
    from devrel.search.github_client import GitHubClient

    # 1. Basic doc gap analysis
    base_gap = detect_doc_gaps_llm(llm, issues)

    # 2. Initialize GitHub client
    github = GitHubClient(token=github_token)

    # 3. Auto-detect reference repos if not provided
    if not reference_repos:
        reference_repos = github.search_similar_repos(
            topic=base_gap.gap_topic,
            language="python",
        )

    # 4. Get target repo docs structure
    target_docs_raw = github.get_docs_structure(target_repo)
    target_docs = None
    if target_docs_raw:
        target_docs = RepoDocsInfo(
            repo=target_docs_raw.repo,
            docs_path=target_docs_raw.docs_path,
            files=tuple(
                RepoDocFile(path=f.path, name=f.name, url=f.url)
                for f in target_docs_raw.files
            ),
            topics=target_docs_raw.topics,
            total_files=target_docs_raw.total_files,
        )

    # 5. Get reference repos docs structures and compare
    ref_docs_list = []
    all_missing_topics = set()
    all_reference_examples = []

    for ref_repo in reference_repos[:3]:  # Limit to 3 reference repos
        comparison = github.compare_docs(target_repo, ref_repo)

        if comparison.reference_docs:
            ref_info = RepoDocsInfo(
                repo=comparison.reference_docs.repo,
                docs_path=comparison.reference_docs.docs_path,
                files=tuple(
                    RepoDocFile(path=f.path, name=f.name, url=f.url)
                    for f in comparison.reference_docs.files
                ),
                topics=comparison.reference_docs.topics,
                total_files=comparison.reference_docs.total_files,
            )
            ref_docs_list.append(ref_info)

            # Collect missing topics
            all_missing_topics.update(comparison.missing_topics)

            # Collect example docs related to the gap topic
            gap_topic_lower = base_gap.gap_topic.lower()
            for f in comparison.reference_docs.files:
                if gap_topic_lower in f.name.lower() or gap_topic_lower in f.path.lower():
                    all_reference_examples.append(
                        RepoDocFile(path=f.path, name=f.name, url=f.url)
                    )

    # 6. Calculate overall coverage
    if ref_docs_list and target_docs:
        all_ref_topics = set()
        for ref in ref_docs_list:
            all_ref_topics.update(ref.topics)
        target_topics = set(target_docs.topics)
        coverage = len(target_topics & all_ref_topics) / len(all_ref_topics) if all_ref_topics else 1.0
    else:
        coverage = 0.0

    # 7. Generate suggestions
    suggestions = []
    if all_missing_topics:
        suggestions.append(f"Missing documentation topics: {', '.join(sorted(all_missing_topics)[:5])}")
    if all_reference_examples:
        example_repos = set(f.path.split("/")[0] if "/" in f.path else "" for f in all_reference_examples[:3])
        suggestions.append(f"Reference examples found in: {', '.join(r for r in example_repos if r)}")
    if coverage < 0.5:
        suggestions.append(f"Documentation coverage is {coverage:.0%}. Consider adding more docs.")

    # 8. Generate suggested structure based on reference repos
    suggested_structure = list(base_gap.suggested_outline)
    for topic in sorted(all_missing_topics)[:3]:
        if topic not in [s.lower() for s in suggested_structure]:
            suggested_structure.append(topic.title())

    # 9. Build comparison result
    docs_comparison = DocsComparisonResult(
        target_repo=target_repo,
        reference_repos=tuple(reference_repos[:3]),
        target_docs=target_docs,
        reference_docs=tuple(ref_docs_list),
        missing_topics=tuple(sorted(all_missing_topics)),
        missing_docs=(base_gap.suggested_doc_path,),
        coverage_ratio=coverage,
        suggestions=tuple(suggestions),
    )

    return GitHubEnhancedDocGapOutput(
        gap_analysis=base_gap,
        docs_comparison=docs_comparison,
        reference_examples=tuple(all_reference_examples[:5]),
        suggested_structure=tuple(suggested_structure),
    )


@dataclass(frozen=True, slots=True)
class FullDocGapAnalysis:
    """Complete doc gap analysis combining GitHub docs comparison and Tavily insights."""
    gap_analysis: DocGapOutput
    # GitHub API results
    docs_comparison: DocsComparisonResult | None
    reference_examples: tuple[RepoDocFile, ...]
    # Tavily results
    tavily_insights: tuple[ExternalDocReference, ...]
    best_practices: str | None
    tavily_answer: str | None
    # Combined suggestions
    suggested_structure: tuple[str, ...]
    action_items: tuple[str, ...]


def detect_doc_gaps_full(
    llm: LlmClient,
    issues: list[Issue],
    target_repo: str,
    reference_repos: list[str] | None = None,
    github_token: str | None = None,
    tavily_api_key: str | None = None,
) -> FullDocGapAnalysis:
    """Detect documentation gaps using both GitHub API and Tavily.

    Combines:
    - GitHub API: Direct docs structure comparison with reference repos
    - Tavily: External insights, best practices, and AI summaries

    Args:
        llm: LLM client
        issues: List of issues to analyze
        target_repo: Target repository name (e.g., "openai/openai-agents-python")
        reference_repos: List of reference repos to compare (auto-detected if None)
        github_token: GitHub token (or set GITHUB_TOKEN env var)
        tavily_api_key: Tavily API key (or set TAVILY_API_KEY env var)
    """
    from devrel.search.github_client import GitHubClient
    from devrel.search.tavily_client import TavilyClient

    # 1. Basic doc gap analysis via LLM
    base_gap = detect_doc_gaps_llm(llm, issues)

    # ========== GitHub API ==========
    github = GitHubClient(token=github_token)

    # Auto-detect reference repos if not provided
    if not reference_repos:
        reference_repos = github.search_similar_repos(
            topic=base_gap.gap_topic,
            language="python",
        )
        # Fallback to common Python repos if search returns empty
        if not reference_repos:
            reference_repos = ["redis/redis-py", "psf/requests", "pallets/flask"]

    # Get target repo docs structure
    target_docs_raw = github.get_docs_structure(target_repo)
    target_docs = None
    if target_docs_raw:
        target_docs = RepoDocsInfo(
            repo=target_docs_raw.repo,
            docs_path=target_docs_raw.docs_path,
            files=tuple(
                RepoDocFile(path=f.path, name=f.name, url=f.url)
                for f in target_docs_raw.files
            ),
            topics=target_docs_raw.topics,
            total_files=target_docs_raw.total_files,
        )

    # Compare with reference repos
    ref_docs_list = []
    all_missing_topics = set()
    all_reference_examples = []

    for ref_repo in reference_repos[:3]:
        comparison = github.compare_docs(target_repo, ref_repo)
        if comparison.reference_docs:
            ref_info = RepoDocsInfo(
                repo=comparison.reference_docs.repo,
                docs_path=comparison.reference_docs.docs_path,
                files=tuple(
                    RepoDocFile(path=f.path, name=f.name, url=f.url)
                    for f in comparison.reference_docs.files
                ),
                topics=comparison.reference_docs.topics,
                total_files=comparison.reference_docs.total_files,
            )
            ref_docs_list.append(ref_info)
            all_missing_topics.update(comparison.missing_topics)

            # Collect example docs related to the gap topic
            gap_topic_lower = base_gap.gap_topic.lower()
            for f in comparison.reference_docs.files:
                if gap_topic_lower in f.name.lower() or gap_topic_lower in f.path.lower():
                    all_reference_examples.append(
                        RepoDocFile(path=f.path, name=f.name, url=f.url)
                    )

    # Calculate coverage
    if ref_docs_list and target_docs:
        all_ref_topics = set()
        for ref in ref_docs_list:
            all_ref_topics.update(ref.topics)
        target_topics = set(target_docs.topics)
        coverage = len(target_topics & all_ref_topics) / len(all_ref_topics) if all_ref_topics else 1.0
    else:
        coverage = 0.0

    docs_comparison = DocsComparisonResult(
        target_repo=target_repo,
        reference_repos=tuple(reference_repos[:3]),
        target_docs=target_docs,
        reference_docs=tuple(ref_docs_list),
        missing_topics=tuple(sorted(all_missing_topics)),
        missing_docs=(base_gap.suggested_doc_path,),
        coverage_ratio=coverage,
        suggestions=(),
    )

    # ========== Tavily API ==========
    tavily = TavilyClient(api_key=tavily_api_key)

    # Search for similar repos and best practices
    similar_insight = tavily.search_similar_repos(
        repo_name=target_repo,
        topic=f"{base_gap.gap_topic} documentation",
    )

    best_practices_insight = tavily.search_docs_best_practices(
        topic=base_gap.gap_topic,
        repo_type="python agent framework",
    )

    # Extract external doc references from Tavily
    tavily_refs = []
    for result in similar_insight.results[:5]:
        if "github.com" in result.url:
            parts = result.url.replace("https://github.com/", "").split("/")
            repo = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else ""
            doc_path = "/".join(parts[2:]) if len(parts) > 2 else ""
            tavily_refs.append(
                ExternalDocReference(
                    repo=repo,
                    doc_path=doc_path,
                    url=result.url,
                    description=result.content[:200] if result.content else "",
                    relevance=result.score,
                )
            )

    # ========== Combine Results ==========
    # Build suggested structure from LLM + missing topics
    suggested_structure = list(base_gap.suggested_outline)
    for topic in sorted(all_missing_topics)[:3]:
        if topic not in [s.lower() for s in suggested_structure]:
            suggested_structure.append(topic.title())

    # Generate action items
    action_items = []
    if base_gap.has_gap:
        action_items.append(f"Create {base_gap.suggested_doc_path} for {base_gap.gap_topic}")
    if all_missing_topics:
        action_items.append(f"Add documentation for: {', '.join(sorted(all_missing_topics)[:3])}")
    if all_reference_examples:
        action_items.append(f"Reference: {all_reference_examples[0].url}")
    if best_practices_insight.answer:
        action_items.append(f"Best practice: {best_practices_insight.answer[:100]}...")

    return FullDocGapAnalysis(
        gap_analysis=base_gap,
        docs_comparison=docs_comparison,
        reference_examples=tuple(all_reference_examples[:5]),
        tavily_insights=tuple(tavily_refs),
        best_practices=best_practices_insight.answer,
        tavily_answer=similar_insight.answer,
        suggested_structure=tuple(suggested_structure),
        action_items=tuple(action_items),
    )
