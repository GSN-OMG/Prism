"""Tests for raw_data CSV loading and conversion."""
import pytest

from tests.helpers.raw_data_loader import (
    build_contributors_from_raw_data,
    get_active_contributors,
    get_issue_numbers_from_activities,
    load_repo_users,
    load_user_activities,
)

REPO = "openai/openai-agents-python"


class TestRawDataLoader:
    def test_load_repo_users(self) -> None:
        users = load_repo_users(REPO)
        assert len(users) > 0
        # Check structure
        first = users[0]
        assert first.user_id
        assert first.role in ("CONTRIBUTOR", "COLLABORATOR", "MEMBER", "NONE")

    def test_load_user_activities(self) -> None:
        activities = load_user_activities(REPO)
        assert len(activities) > 0
        # Check structure
        first = activities[0]
        assert first.user_id
        assert first.action in (
            "issue_opened",
            "pr_opened",
            "commented",
            "reviewed",
            "labeled",
            "closed",
            "reopened",
        )
        assert first.reference.startswith("https://github.com/")
        assert first.occurred_at is not None

    def test_build_contributors_from_raw_data(self) -> None:
        contributors = build_contributors_from_raw_data(REPO)
        assert len(contributors) > 0
        # Check Contributor structure
        for c in contributors[:5]:
            assert c.login
            assert isinstance(c.areas, tuple)
            assert isinstance(c.recent_activity_score, float)
            assert isinstance(c.merged_prs, int)
            assert isinstance(c.reviews, int)

    def test_get_active_contributors(self) -> None:
        active = get_active_contributors(REPO, min_activity=3)
        # Should have fewer than all contributors
        all_contributors = build_contributors_from_raw_data(REPO)
        assert len(active) <= len(all_contributors)
        # All returned should meet threshold
        for c in active:
            assert c.merged_prs + c.reviews >= 3

    def test_get_issue_numbers_from_activities(self) -> None:
        issues = get_issue_numbers_from_activities(REPO)
        assert len(issues) > 0
        assert all(isinstance(n, int) for n in issues)
        assert all(n > 0 for n in issues)

    def test_contributor_areas_inferred(self) -> None:
        contributors = build_contributors_from_raw_data(REPO)
        # Find a contributor with reviews
        reviewers = [c for c in contributors if c.reviews > 0]
        if reviewers:
            assert "code-review" in reviewers[0].areas

    def test_activity_score_range(self) -> None:
        contributors = build_contributors_from_raw_data(REPO)
        for c in contributors:
            assert c.recent_activity_score >= 0.0
