from tests.helpers.github_fixtures import (
    contributor_from_profile_json,
    issue_from_github_json,
    load_json,
)

from devrel.agents.assignment import analyze_issue, recommend_assignee
from devrel.agents.docs import detect_doc_gaps, to_doc_gap_output
from devrel.agents.response import draft_response
from devrel.agents.types import IssueType, ResponseStrategy


def test_fixture_oauth_bug_analysis_and_assignment() -> None:
    issue = issue_from_github_json(load_json("github/issue_bug_oauth.json"))
    contributors = [contributor_from_profile_json(c) for c in load_json("github/contributors.json")]

    analysis = analyze_issue(issue)
    assert analysis.issue_type == IssueType.BUG
    assert "auth" in analysis.required_skills

    assignment = recommend_assignee(analysis, contributors, limit=3)
    assert assignment.recommended_assignee in {"alice", "bob", "carol"}
    assert 0.0 <= assignment.confidence <= 1.0


def test_fixture_question_logging_requests_info() -> None:
    issue = issue_from_github_json(load_json("github/issue_question_logging.json"))
    analysis = analyze_issue(issue)
    response = draft_response(issue, analysis)
    assert response.strategy == ResponseStrategy.REQUEST_INFO


def test_fixture_docs_redis_produces_doc_gap_output() -> None:
    issues = [
        issue_from_github_json(load_json("github/issue_docs_redis.json")),
        issue_from_github_json(load_json("github/issue_bug_oauth.json")),
    ]
    gaps = detect_doc_gaps(issues)
    assert gaps

    redis = next((g for g in gaps if g.topic == "redis"), None)
    assert redis is not None

    output = to_doc_gap_output(redis)
    assert output.has_gap is True
    assert output.gap_topic == "redis"
    assert output.suggested_doc_path

