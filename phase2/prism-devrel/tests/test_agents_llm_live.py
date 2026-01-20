import os

import pytest

from devrel.agents.assignment import analyze_issue_llm, recommend_assignee_llm
from devrel.agents.docs import detect_doc_gaps_llm
from devrel.agents.promotion import evaluate_promotion_llm
from devrel.agents.response import draft_response_llm
from devrel.llm.client import LlmClient
from tests.helpers.github_fixtures import contributor_from_profile_json, issue_from_github_json, load_json


@pytest.mark.llm_live
def test_live_llm_end_to_end_on_fixtures() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    os.environ.setdefault("OPENAI_MODEL_ISSUE_TRIAGE", "gpt-4.1-mini")
    os.environ.setdefault("OPENAI_MODEL_ASSIGNMENT", "gpt-4.1-mini")
    os.environ.setdefault("OPENAI_MODEL_RESPONSE", "gpt-4.1-mini")
    os.environ.setdefault("OPENAI_MODEL_DOCS", "gpt-4.1-mini")
    os.environ.setdefault("OPENAI_MODEL_PROMOTION", "gpt-4.1-mini")

    llm = LlmClient()

    issues = [
        issue_from_github_json(load_json("github/issue_bug_oauth.json")),
        issue_from_github_json(load_json("github/issue_question_logging.json")),
        issue_from_github_json(load_json("github/issue_docs_redis.json")),
    ]
    contributors = [contributor_from_profile_json(c) for c in load_json("github/contributors.json")]

    for issue in issues:
        analysis = analyze_issue_llm(llm, issue)
        assert analysis.summary
        assert analysis.required_skills is not None

        assignment = recommend_assignee_llm(
            llm, issue=issue, issue_analysis=analysis, contributors=contributors, limit=3
        )
        allowed = {c.login for c in contributors}
        assert assignment.recommended_assignee in allowed
        assert 0.0 <= assignment.confidence <= 1.0

        resp = draft_response_llm(llm, issue=issue, analysis=analysis, references=[])
        assert resp.response_text.strip()
        assert 0.0 <= resp.confidence <= 1.0

    gap = detect_doc_gaps_llm(llm, issues)
    assert gap.has_gap in (True, False)
    if gap.has_gap:
        assert set(gap.affected_issues).issubset({i.number for i in issues})
        assert gap.suggested_doc_path
        assert gap.suggested_outline

    promo = evaluate_promotion_llm(llm, contributors[0])
    assert promo.current_stage
    assert promo.suggested_stage
    assert 0.0 <= promo.confidence <= 1.0

