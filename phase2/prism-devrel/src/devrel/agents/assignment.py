from __future__ import annotations

from .types import AssigneeRecommendation, Contributor, Issue, IssueAnalysis, IssueKind


def analyze_issue(issue: Issue) -> IssueAnalysis:
    title_lower = issue.title.lower()
    labels_lower = {label.lower() for label in issue.labels}

    if "bug" in labels_lower or "fail" in title_lower or "error" in title_lower:
        kind = IssueKind.BUG
    elif "documentation" in labels_lower or "docs" in title_lower:
        kind = IssueKind.DOCUMENTATION
    elif "?" in issue.title or "question" in labels_lower:
        kind = IssueKind.QUESTION
    else:
        kind = IssueKind.UNKNOWN

    missing: list[str] = []
    if not issue.body.strip():
        missing.append("Could you share steps to reproduce and expected vs actual behavior?")

    suggested: list[str] = []
    if kind == IssueKind.BUG and "bug" not in labels_lower:
        suggested.append("bug")
    if kind == IssueKind.DOCUMENTATION and "documentation" not in labels_lower:
        suggested.append("documentation")

    return IssueAnalysis(
        kind=kind,
        summary=issue.title.strip() or "No title",
        missing_info_questions=tuple(missing),
        suggested_labels=tuple(suggested),
    )


def recommend_assignees(
    issue_analysis: IssueAnalysis,
    contributors: list[Contributor],
    *,
    limit: int = 3,
) -> list[AssigneeRecommendation]:
    def score_contributor(contributor: Contributor) -> float:
        base = contributor.recent_activity_score
        if issue_analysis.kind == IssueKind.DOCUMENTATION and "docs" in contributor.areas:
            base += 1.0
        if issue_analysis.kind == IssueKind.BUG and "backend" in contributor.areas:
            base += 0.5
        return base

    ranked = sorted(contributors, key=score_contributor, reverse=True)
    results: list[AssigneeRecommendation] = []
    for contributor in ranked[: max(limit, 0)]:
        results.append(
            AssigneeRecommendation(
                login=contributor.login,
                score=score_contributor(contributor),
                rationale=f"Matched on kind={issue_analysis.kind.value} and recent activity.",
            )
        )
    return results

