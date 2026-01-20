import os

import pytest

from devrel.agents.assignment import analyze_issue
from devrel.agents.response import draft_response
from tests.helpers.github_fixtures import issue_from_github_json, load_json
from tests.helpers.llm_judge import judge_response_text


@pytest.mark.llm_judge
def test_llm_judges_response_quality_on_logging_question() -> None:
    if os.getenv("RUN_LLM_JUDGE", "0") not in ("1", "true", "TRUE", "yes", "YES"):
        pytest.skip("RUN_LLM_JUDGE not enabled")

    issue = issue_from_github_json(load_json("github/issue_question_logging.json"))
    analysis = analyze_issue(issue)
    response = draft_response(issue, analysis)

    result = judge_response_text(issue=issue, analysis=analysis, response_text=response.response_text)
    assert result.passed is True
    assert result.score >= 7

