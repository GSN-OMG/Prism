"""Tests for agents using real raw_data from CSV files."""
import pytest

from devrel.agents.assignment import recommend_assignee, recommend_assignee_llm
from devrel.agents.promotion import evaluate_promotion, evaluate_promotion_llm
from devrel.agents.types import Issue, IssueAnalysisOutput, IssueType, Priority, ResponseStrategy
from devrel.llm.client import LlmClient
from tests.helpers.raw_data_loader import build_contributors_from_raw_data, get_active_contributors

REPO = "openai/openai-agents-python"

# Valid stages from promotion.py
VALID_STAGES = ("NEW", "FIRST_TIMER", "REGULAR", "CORE", "MAINTAINER")


def make_sample_issue() -> Issue:
    """Create a sample issue for testing."""
    return Issue(
        number=2314,
        title="OAuth token refresh not working with custom providers",
        body=(
            "When using a custom OAuth provider, the token refresh mechanism fails. "
            "The SDK returns 401 errors after the initial token expires. "
            "Expected: automatic token refresh. Actual: connection fails."
        ),
        labels=("bug", "auth"),
    )


def make_sample_analysis() -> IssueAnalysisOutput:
    """Create a sample issue analysis for testing."""
    return IssueAnalysisOutput(
        issue_type=IssueType.BUG,
        priority=Priority.HIGH,
        required_skills=("auth", "oauth", "debugging"),
        keywords=("oauth", "token", "refresh", "401"),
        summary="OAuth token refresh failing with custom providers",
        needs_more_info=False,
        suggested_action=ResponseStrategy.DIRECT_ANSWER,
    )


class TestAssignmentWithRawData:
    def test_recommend_assignee_with_real_contributors(self) -> None:
        """Test assignee recommendation using real contributor data."""
        contributors = get_active_contributors(REPO, min_activity=2)
        assert len(contributors) > 0, "Should have active contributors"

        analysis = make_sample_analysis()

        # recommend_assignee takes (issue_analysis, contributors, *, limit)
        result = recommend_assignee(analysis, contributors, limit=3)

        # Should recommend someone from the contributor list
        logins = {c.login for c in contributors}
        assert result.recommended_assignee in logins
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.alternative_assignees) <= 2

    def test_recommend_assignee_respects_limit(self) -> None:
        """Test that alternative assignees respect the limit."""
        contributors = get_active_contributors(REPO, min_activity=1)
        analysis = make_sample_analysis()

        result = recommend_assignee(analysis, contributors, limit=5)
        # alternatives = limit - 1 (excluding recommended)
        assert len(result.alternative_assignees) <= 4


class TestPromotionWithRawData:
    def test_evaluate_promotion_with_real_contributors(self) -> None:
        """Test promotion evaluation using real contributor data."""
        contributors = build_contributors_from_raw_data(REPO)
        assert len(contributors) > 0

        # Test with a few contributors
        for contributor in contributors[:5]:
            result = evaluate_promotion(contributor)
            assert result.current_stage in VALID_STAGES
            assert result.suggested_stage in VALID_STAGES
            assert 0.0 <= result.confidence <= 1.0
            assert isinstance(result.is_candidate, bool)

    def test_active_contributor_has_higher_stage(self) -> None:
        """Test that active contributors get appropriate stage."""
        active = get_active_contributors(REPO, min_activity=5)
        if not active:
            pytest.skip("No highly active contributors found")

        result = evaluate_promotion(active[0])
        # Active contributors should not be "NEW"
        assert result.current_stage in ("FIRST_TIMER", "REGULAR", "CORE", "MAINTAINER")


@pytest.mark.llm_live
class TestAgentsWithRawDataLLM:
    """LLM-based tests using real raw_data."""

    def test_recommend_assignee_llm_with_real_data(self) -> None:
        """Test LLM-based assignee recommendation with real contributors."""
        llm = LlmClient()
        contributors = get_active_contributors(REPO, min_activity=3)
        if len(contributors) < 3:
            pytest.skip("Not enough active contributors")

        issue = make_sample_issue()
        analysis = make_sample_analysis()

        result = recommend_assignee_llm(
            llm, issue=issue, issue_analysis=analysis, contributors=contributors[:10], limit=3
        )

        logins = {c.login for c in contributors[:10]}
        assert result.recommended_assignee in logins
        assert 0.0 <= result.confidence <= 1.0
        assert result.context_for_assignee

    def test_evaluate_promotion_llm_with_real_data(self) -> None:
        """Test LLM-based promotion evaluation with real contributors."""
        llm = LlmClient()
        active = get_active_contributors(REPO, min_activity=5)
        if not active:
            pytest.skip("No highly active contributors")

        result = evaluate_promotion_llm(llm, active[0])
        assert result.current_stage
        assert result.suggested_stage
        assert 0.0 <= result.confidence <= 1.0
        assert result.recommendation
