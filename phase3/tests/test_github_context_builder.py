from __future__ import annotations

from typing import Any, Mapping

from prism.phase3.github_context_builder import build_github_context_bundle


class _FakeGitHubClient:
    def __init__(self) -> None:
        self.rate_limit_events = 0
        self.last_rate_limit = None

    def request_json(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        del headers
        if path == "/repos/acme/widget/issues/42":
            return {
                "id": 1001,
                "number": 42,
                "title": "Add new widget API",
                "html_url": "https://github.com/acme/widget/pull/42",
                "state": "closed",
                "created_at": "2026-01-20T00:00:00Z",
                "closed_at": "2026-01-21T00:00:00Z",
                "user": {"login": "contributor", "type": "User"},
                "labels": [{"name": "feature"}],
                "assignees": [{"login": "maintainer"}],
            }
        if path == "/repos/acme/widget/pulls/42":
            return {
                "id": 2001,
                "number": 42,
                "title": "Add new widget API",
                "html_url": "https://github.com/acme/widget/pull/42",
                "state": "closed",
                "created_at": "2026-01-20T00:00:00Z",
                "merged_at": "2026-01-21T00:00:00Z",
                "head": {"sha": "abc123"},
            }
        if path == "/repos/acme/widget/commits/abc123/check-runs":
            assert query == {"per_page": 100}
            return {
                "check_runs": [
                    {
                        "id": 5001,
                        "name": "CI",
                        "status": "completed",
                        "conclusion": "success",
                        "completed_at": "2026-01-20T03:00:00Z",
                        "details_url": "https://github.com/acme/widget/actions/runs/1",
                    }
                ]
            }
        raise AssertionError(f"unexpected request_json path: {path}")

    def paginate(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int = 10,
        item_key: str | None = None,
    ) -> list[Any]:
        del query, per_page, max_pages, item_key
        if path == "/repos/acme/widget/issues/42/events":
            return []
        if path == "/repos/acme/widget/issues/42/comments":
            return [
                {
                    "id": 3001,
                    "created_at": "2026-01-20T01:00:00Z",
                    "body": "Thanks! I'll take a look.",
                    "html_url": "https://github.com/acme/widget/pull/42#issuecomment-3001",
                    "user": {"login": "devrel-bot", "type": "User"},
                }
            ]
        if path == "/repos/acme/widget/pulls/42/reviews":
            return [
                {
                    "id": 4001,
                    "submitted_at": "2026-01-20T02:00:00Z",
                    "state": "APPROVED",
                    "body": "",
                    "html_url": "https://github.com/acme/widget/pull/42#pullrequestreview-4001",
                    "user": {"login": "devrel-bot", "type": "User"},
                }
            ]
        if path == "/repos/acme/widget/pulls/42/comments":
            return []
        if path == "/repos/acme/widget/pulls/42/files":
            return [
                {
                    "filename": "src/widget.js",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 2,
                    "changes": 12,
                }
            ]
        raise AssertionError(f"unexpected paginate path: {path}")


def test_builds_context_bundle_for_pr_with_metrics_and_events() -> None:
    bundle = build_github_context_bundle(
        repo="acme/widget",
        type="pull_request",
        number=42,
        token="ghp_NOT_A_REAL_TOKEN",
        max_pages=1,
        agent_map_json='{"devrel-bot":{"id":"devrel-pr-reviewer-1","role":"devrel-pr-reviewer"}}',
        client=_FakeGitHubClient(),
    )

    assert bundle["source"]["system"] == "github"
    assert bundle["source"]["repo"] == "acme/widget"
    assert bundle["metadata"]["github"]["number"] == 42
    assert bundle["metadata"]["github"]["state"] == "merged"

    metrics = bundle["result"]["metrics"]
    assert metrics["time_to_first_response_sec"] == 3600
    assert metrics["time_to_merge_sec"] == 86400
    assert metrics["num_comments"] == 1
    assert metrics["num_review_comments"] == 0

    event_types = [e["event_type"] for e in bundle["events"]]
    assert "github.pull_request.opened" in event_types
    assert "github.pull_request.comment.created" in event_types
    assert "github.review.submitted" in event_types
    assert "github.ci.check_run.completed" in event_types

    assert any(e["actor_type"] == "ai" for e in bundle["events"])
    assert any(a["id"] == "devrel-pr-reviewer-1" for a in bundle["agents"])

    assert any(
        a.get("type") == "github.pull_request.files" and a.get("count") == 1
        for a in bundle["result"]["artifacts"]
    )
