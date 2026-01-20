from __future__ import annotations

import json

from devrel.llm.client import JsonSchema, LlmClient
from devrel.llm.model_selector import LlmTask

from .types import (
    AssignmentOutput,
    AssignmentReason,
    Contributor,
    Issue,
    IssueAnalysisOutput,
    IssueType,
    Priority,
    ResponseStrategy,
    assignment_output_from_dict,
    issue_analysis_from_dict,
)


def analyze_issue(issue: Issue) -> IssueAnalysisOutput:
    title_lower = issue.title.lower()
    labels_lower = {label.lower() for label in issue.labels}

    if {"bug", "crash", "regression"} & labels_lower or any(
        token in title_lower for token in ("fail", "error", "exception", "stack trace", "crash")
    ):
        issue_type = IssueType.BUG
    elif "documentation" in labels_lower or "docs" in title_lower or "readme" in title_lower:
        issue_type = IssueType.DOCUMENTATION
    elif "feature" in labels_lower or any(token in title_lower for token in ("feature", "support", "add ")):
        issue_type = IssueType.FEATURE
    elif "?" in issue.title or "question" in labels_lower or "how do i" in title_lower:
        issue_type = IssueType.QUESTION
    else:
        issue_type = IssueType.OTHER

    combined = f"{issue.title}\n\n{issue.body}".lower()
    keywords = _extract_keywords(combined)
    required_skills = _infer_required_skills(issue_type, keywords)

    needs_more_info = not issue.body.strip()
    suggested_action = (
        ResponseStrategy.REQUEST_INFO if needs_more_info else ResponseStrategy.DIRECT_ANSWER
    )

    priority = _infer_priority(issue_type, combined)

    summary = issue.title.strip() or f"Issue #{issue.number}"

    return IssueAnalysisOutput(
        issue_type=issue_type,
        priority=priority,
        required_skills=tuple(required_skills),
        keywords=tuple(keywords),
        summary=summary,
        needs_more_info=needs_more_info,
        suggested_action=suggested_action,
    )


def analyze_issue_llm(llm: LlmClient, issue: Issue) -> IssueAnalysisOutput:
    schema = JsonSchema(
        name="issue_analysis_output",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "issue_type": {"type": "string", "enum": [t.value for t in IssueType]},
                "priority": {"type": "string", "enum": [p.value for p in Priority]},
                "required_skills": {"type": "array", "items": {"type": "string"}},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
                "needs_more_info": {"type": "boolean"},
                "suggested_action": {"type": "string", "enum": [s.value for s in ResponseStrategy]},
            },
            "required": [
                "issue_type",
                "priority",
                "required_skills",
                "keywords",
                "summary",
                "needs_more_info",
                "suggested_action",
            ],
        },
    )

    system = (
        "You are a DevRel agent that triages GitHub issues.\n"
        "Return only the requested JSON schema.\n"
        "If information is missing, set needs_more_info=true and suggested_action=request_info."
    )
    user = (
        f"Issue number: {issue.number}\n"
        f"Title: {issue.title}\n"
        f"Body: {issue.body}\n"
        f"Labels: {list(issue.labels)}\n"
    )
    data = llm.generate_json(task=LlmTask.ISSUE_TRIAGE, system=system, user=user, json_schema=schema)
    return issue_analysis_from_dict(data)


def recommend_assignee(
    issue_analysis: IssueAnalysisOutput,
    contributors: list[Contributor],
    *,
    limit: int = 3,
) -> AssignmentOutput:
    if not contributors or limit <= 0:
        return AssignmentOutput(
            recommended_assignee="",
            confidence=0.0,
            reasons=(),
            context_for_assignee="",
            alternative_assignees=(),
        )

    ranked = sorted(contributors, key=lambda c: _score_contributor(issue_analysis, c), reverse=True)
    top = ranked[0]
    top_score = _score_contributor(issue_analysis, top)
    second_score = _score_contributor(issue_analysis, ranked[1]) if len(ranked) > 1 else 0.0

    confidence = 0.5
    if top_score > 0:
        confidence = min(1.0, 0.5 + (top_score - second_score) / max(top_score, 1.0))

    reasons = _build_reasons(issue_analysis, top)
    alternatives = tuple(c.login for c in ranked[1:max(limit, 1)])

    context = (
        f"Issue type: {issue_analysis.issue_type.value}\n"
        f"Priority: {issue_analysis.priority.value}\n"
        f"Keywords: {', '.join(issue_analysis.keywords) if issue_analysis.keywords else 'n/a'}\n"
        f"Suggested action: {issue_analysis.suggested_action.value}\n"
    )

    return AssignmentOutput(
        recommended_assignee=top.login,
        confidence=float(confidence),
        reasons=tuple(reasons),
        context_for_assignee=context,
        alternative_assignees=alternatives,
    )


def recommend_assignee_llm(
    llm: LlmClient,
    *,
    issue: Issue,
    issue_analysis: IssueAnalysisOutput,
    contributors: list[Contributor],
    limit: int = 3,
) -> AssignmentOutput:
    schema = JsonSchema(
        name="assignment_output",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "recommended_assignee": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reasons": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "factor": {"type": "string"},
                            "explanation": {"type": "string"},
                            "score": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["factor", "explanation", "score"],
                    },
                },
                "context_for_assignee": {"type": "string"},
                "alternative_assignees": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "recommended_assignee",
                "confidence",
                "reasons",
                "context_for_assignee",
                "alternative_assignees",
            ],
        },
    )

    system = (
        "You are a DevRel assignment agent.\n"
        "Pick the best assignee among the provided candidates.\n"
        "Return only JSON and do not invent contributors outside the list."
    )
    payload = {
        "issue": {"number": issue.number, "title": issue.title, "body": issue.body, "labels": list(issue.labels)},
        "analysis": {
            "issue_type": issue_analysis.issue_type.value,
            "priority": issue_analysis.priority.value,
            "required_skills": list(issue_analysis.required_skills),
            "keywords": list(issue_analysis.keywords),
            "summary": issue_analysis.summary,
            "needs_more_info": issue_analysis.needs_more_info,
            "suggested_action": issue_analysis.suggested_action.value,
        },
        "contributors": [
            {
                "login": c.login,
                "areas": list(c.areas),
                "recent_activity_score": c.recent_activity_score,
                "merged_prs": c.merged_prs,
                "reviews": c.reviews,
            }
            for c in contributors
        ],
        "limit": limit,
    }
    user = f"Input:\n{json.dumps(payload, ensure_ascii=False)}"
    data = llm.generate_json(task=LlmTask.ASSIGNMENT, system=system, user=user, json_schema=schema)
    out = assignment_output_from_dict(data)

    allowed = {c.login for c in contributors}
    if out.recommended_assignee and out.recommended_assignee not in allowed:
        return recommend_assignee(issue_analysis, contributors, limit=limit)
    return out


def _infer_priority(issue_type: IssueType, text: str) -> Priority:
    if any(token in text for token in ("critical", "security", "data loss", "breach")):
        return Priority.CRITICAL
    if any(token in text for token in ("crash", "regression", "downtime", "outage")):
        return Priority.HIGH
    if issue_type in (IssueType.BUG, IssueType.DOCUMENTATION):
        return Priority.MEDIUM
    return Priority.LOW


def _extract_keywords(text: str) -> list[str]:
    hits: list[str] = []
    for token in ("oauth", "auth", "redis", "cache", "logging", "debug", "api", "timeout"):
        if token in text and token not in hits:
            hits.append(token)
    return hits


def _infer_required_skills(issue_type: IssueType, keywords: list[str]) -> list[str]:
    skills: list[str] = []
    if issue_type == IssueType.DOCUMENTATION:
        skills.append("docs")
    if issue_type == IssueType.BUG:
        skills.append("debugging")
    if "oauth" in keywords or "auth" in keywords:
        skills.append("auth")
    if "redis" in keywords or "cache" in keywords:
        skills.append("cache")
    return skills


def _score_contributor(issue_analysis: IssueAnalysisOutput, contributor: Contributor) -> float:
    score = min(contributor.recent_activity_score, 2.0)

    required = set(issue_analysis.required_skills)
    areas = set(contributor.areas)
    if required and areas:
        overlap = len(required & areas)
        score += overlap * 2.0

    score += min(contributor.merged_prs, 10) * 0.05
    score += min(contributor.reviews, 20) * 0.02
    return float(score)


def _build_reasons(issue_analysis: IssueAnalysisOutput, contributor: Contributor) -> list[AssignmentReason]:
    reasons: list[AssignmentReason] = []
    overlap = sorted(set(issue_analysis.required_skills) & set(contributor.areas))
    if overlap:
        reasons.append(
            AssignmentReason(
                factor="skill_match",
                explanation=f"Overlapping areas: {', '.join(overlap)}",
                score=min(1.0, 0.3 + 0.2 * len(overlap)),
            )
        )
    reasons.append(
        AssignmentReason(
            factor="recent_activity",
            explanation=f"recent_activity_score={contributor.recent_activity_score}",
            score=min(1.0, contributor.recent_activity_score / 5.0),
        )
    )
    if contributor.merged_prs:
        reasons.append(
            AssignmentReason(
                factor="merged_prs",
                explanation=f"merged_prs={contributor.merged_prs}",
                score=min(1.0, contributor.merged_prs / 20.0),
            )
        )
    if contributor.reviews:
        reasons.append(
            AssignmentReason(
                factor="reviews",
                explanation=f"reviews={contributor.reviews}",
                score=min(1.0, contributor.reviews / 40.0),
            )
        )
    return reasons
