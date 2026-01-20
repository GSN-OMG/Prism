import unittest


from scripts.build_repo_insights import build_insight_cards


class TestBuildRepoInsights(unittest.TestCase):
    def test_cards_are_bounded(self) -> None:
        repo = "openai/openai-agents-python"
        work_items = {
            (1, "issue"): {
                "number": 1,
                "type": "issue",
                "url": "https://github.com/openai/openai-agents-python/issues/1",
                "title": "Bug: crash",
                "labels": ["bug", "triage"],
                "created_at": "2026-01-01T00:00:00Z",
                "closed_at": "2026-01-02T00:00:00Z",
                "is_merged": False,
            },
            (2, "pr"): {
                "number": 2,
                "type": "pr",
                "url": "https://github.com/openai/openai-agents-python/pull/2",
                "title": "Fix: crash",
                "labels": ["bug"],
                "created_at": "2026-01-01T00:00:00Z",
                "closed_at": "2026-01-02T00:00:00Z",
                "is_merged": True,
            },
        }
        maintainer_comments = [
            {"reference": "https://github.com/openai/openai-agents-python/issues/1", "body_excerpt": "Please share repro steps and logs.", "author_association": "MEMBER"},
            {"reference": "https://github.com/openai/openai-agents-python/issues/1", "body_excerpt": "What version are you on?", "author_association": "MEMBER"},
        ]
        timeline_events = [
            {"reference": "https://github.com/openai/openai-agents-python/issues/1", "event_type": "ClosedEvent", "created_at": "2026-01-02T00:00:00Z"},
            {"reference": "https://github.com/openai/openai-agents-python/issues/1", "event_type": "ReopenedEvent", "created_at": "2026-01-03T00:00:00Z"},
        ]

        cards = build_insight_cards(
            repo_full_name=repo,
            work_items=work_items,
            maintainer_comments=maintainer_comments,
            timeline_events=timeline_events,
            max_cards=5,
            max_evidence=2,
            max_statement_chars=80,
        )
        self.assertLessEqual(len(cards), 5)
        for c in cards:
            self.assertLessEqual(len(c["statement"]), 80)
            self.assertLessEqual(len(c.get("evidence") or []), 2)

