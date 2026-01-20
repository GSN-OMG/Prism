from devrel.agents.assignment import analyze_issue, analyze_issue_llm, recommend_assignee, recommend_assignee_llm
from devrel.agents.docs import detect_doc_gaps, to_doc_gap_output
from devrel.agents.promotion import evaluate_promotion, evaluate_promotion_llm
from devrel.agents.response import draft_response, draft_response_llm
from devrel.agents.types import Contributor, Issue, IssueType, Priority, ResponseStrategy
from devrel.llm.client import JsonSchema
from devrel.llm.model_selector import LlmTask


class FakeLlmClient:
    def __init__(self, mapping: dict[str, dict[str, object]]) -> None:
        self._mapping = mapping

    def generate_json(
        self,
        *,
        task: LlmTask,
        system: str,
        user: str,
        json_schema: JsonSchema,
        temperature: float = 0.2,
        max_output_tokens: int = 600,
    ) -> dict[str, object]:
        _ = (system, user, json_schema, temperature, max_output_tokens)
        return self._mapping[task.value]


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


def test_llm_paths_use_structured_outputs() -> None:
    issue = Issue(number=99, title="Auth error", body="oauth error", labels=("bug",))
    contributors = [
        Contributor(login="alice", areas=("auth",), recent_activity_score=1.0, merged_prs=2, reviews=0),
        Contributor(login="bob", areas=("cache",), recent_activity_score=2.0, merged_prs=1, reviews=0),
    ]

    llm = FakeLlmClient(
        {
            "issue_triage": {
                "issue_type": "bug",
                "priority": "high",
                "required_skills": ["auth"],
                "keywords": ["oauth", "auth"],
                "summary": "Auth error",
                "needs_more_info": False,
                "suggested_action": "direct_answer",
            },
            "assignment": {
                "recommended_assignee": "alice",
                "confidence": 0.9,
                "reasons": [{"factor": "skill_match", "explanation": "auth", "score": 1.0}],
                "context_for_assignee": "context",
                "alternative_assignees": ["bob"],
            },
            "response": {
                "strategy": "direct_answer",
                "response_text": "Try enabling debug logs.",
                "confidence": 0.8,
                "references": [],
                "follow_up_needed": False,
            },
            "promotion": {
                "is_candidate": True,
                "current_stage": "FIRST_TIMER",
                "suggested_stage": "REGULAR",
                "confidence": 0.7,
                "evidence": [{"criterion": "merged_prs", "status": "met", "detail": "2"}],
                "recommendation": "Promote",
            },
        }
    )

    analysis = analyze_issue_llm(llm, issue)
    assert analysis.issue_type == IssueType.BUG

    assignment = recommend_assignee_llm(llm, issue=issue, issue_analysis=analysis, contributors=contributors)
    assert assignment.recommended_assignee == "alice"

    resp = draft_response_llm(llm, issue=issue, analysis=analysis, references=["doc"])
    assert resp.strategy == ResponseStrategy.DIRECT_ANSWER

    promo = evaluate_promotion_llm(llm, contributors[0])
    assert promo.is_candidate is True
