from devrel.agents.assignment import analyze_issue, recommend_assignee
from devrel.agents.docs import detect_doc_gaps, to_doc_gap_output
from devrel.agents.promotion import evaluate_promotion
from devrel.agents.response import draft_response
from devrel.agents.types import Contributor, Issue, IssueType, Priority, ResponseStrategy


def test_analyze_issue_bug_sets_priority_and_action() -> None:
    issue = Issue(
        number=1,
        title="OAuth2 authentication fails with error",
        body="It crashes with stack trace when using OAuth callback.",
        labels=("auth",),
    )
    analysis = analyze_issue(issue)
    assert analysis.issue_type == IssueType.BUG
    assert analysis.priority in (Priority.HIGH, Priority.MEDIUM)
    assert analysis.suggested_action in (ResponseStrategy.DIRECT_ANSWER, ResponseStrategy.ESCALATE)
    assert "oauth" in analysis.keywords


def test_analyze_issue_documentation() -> None:
    issue = Issue(number=20, title="Docs: Redis configuration guide", body="Please add docs", labels=())
    analysis = analyze_issue(issue)
    assert analysis.issue_type == IssueType.DOCUMENTATION
    assert "docs" in analysis.required_skills


def test_analyze_issue_needs_more_info_when_body_missing() -> None:
    issue = Issue(number=2, title="Redis cache setup guide?", body="", labels=("question",))
    analysis = analyze_issue(issue)
    assert analysis.needs_more_info is True
    assert analysis.suggested_action == ResponseStrategy.REQUEST_INFO


def test_recommend_assignee_prefers_skill_overlap() -> None:
    analysis = analyze_issue(
        Issue(number=3, title="Redis cache configuration not working", body="Using redis cache", labels=("bug",))
    )
    contributors = [
        Contributor(login="a", areas=("docs",), recent_activity_score=4.0, merged_prs=1, reviews=0),
        Contributor(login="b", areas=("cache", "debugging"), recent_activity_score=1.0, merged_prs=3, reviews=5),
    ]
    output = recommend_assignee(analysis, contributors, limit=2)
    assert output.recommended_assignee == "b"
    assert 0.0 <= output.confidence <= 1.0
    assert len(output.alternative_assignees) <= 1


def test_recommend_assignee_handles_empty_inputs() -> None:
    analysis = analyze_issue(Issue(number=30, title="Anything", body="", labels=()))
    output = recommend_assignee(analysis, [], limit=3)
    assert output.recommended_assignee == ""
    assert output.confidence == 0.0


def test_draft_response_requests_info_when_needed() -> None:
    issue = Issue(number=4, title="How do I enable debug logging?", body="", labels=("question",))
    analysis = analyze_issue(issue)
    resp = draft_response(issue, analysis)
    assert resp.strategy == ResponseStrategy.REQUEST_INFO
    assert resp.follow_up_needed is True


def test_draft_response_uses_suggested_action_when_info_sufficient() -> None:
    issue = Issue(number=5, title="How do I enable debug logging?", body="I am on v1.2.3", labels=("question",))
    analysis = analyze_issue(issue)
    resp = draft_response(issue, analysis)
    assert resp.strategy == analysis.suggested_action


def test_detect_doc_gaps_and_convert_to_output() -> None:
    issues = [
        Issue(number=10, title="Redis cache setup guide?", body="Need docs", labels=("documentation",)),
        Issue(number=11, title="Redis configuration not working", body="redis error", labels=("bug",)),
        Issue(number=12, title="How to enable debug logging?", body="logging", labels=("question",)),
    ]
    candidates = detect_doc_gaps(issues)
    topics = {c.topic for c in candidates}
    assert "redis" in topics

    redis_candidate = next(c for c in candidates if c.topic == "redis")
    gap = to_doc_gap_output(redis_candidate)
    assert gap.has_gap is True
    assert gap.gap_topic == "redis"
    assert gap.priority in (Priority.HIGH, Priority.MEDIUM)

    logging_candidate = next(c for c in candidates if c.topic == "logging")
    logging_gap = to_doc_gap_output(logging_candidate)
    assert logging_gap.suggested_doc_path


def test_promotion_evaluation() -> None:
    contributor = Contributor(login="contrib", recent_activity_score=3.0, merged_prs=2, reviews=5)
    promo = evaluate_promotion(contributor)
    assert promo.current_stage in ("REGULAR", "FIRST_TIMER", "NEW", "CORE", "MAINTAINER")
    assert 0.0 <= promo.confidence <= 1.0


def test_promotion_stage_progression() -> None:
    c = Contributor(login="c", recent_activity_score=3.0, merged_prs=10, reviews=0)
    promo = evaluate_promotion(c)
    assert promo.current_stage == "CORE"
