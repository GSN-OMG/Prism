import unittest


from scripts.export_repo_work_item_views import (
    extract_rows_from_record,
)


class TestExportRepoWorkItemViews(unittest.TestCase):
    def test_extract_core_issue(self) -> None:
        record = {
            "request": {"body": {"variables": {"owner": "openai", "name": "openai-agents-python", "number": 2206}}},
            "meta": {"tag": "graphql_core_item2206"},
            "response": {
                "json": {
                    "data": {
                        "repository": {
                            "issueOrPullRequest": {
                                "__typename": "Issue",
                                "number": 2206,
                                "url": "https://github.com/openai/openai-agents-python/issues/2206",
                                "title": "feat: Add sessions",
                                "body": "Long body " * 50,
                                "state": "CLOSED",
                                "createdAt": "2026-01-07T00:00:00Z",
                                "closedAt": "2026-01-09T00:00:00Z",
                                "author": {"login": "alice"},
                                "authorAssociation": "CONTRIBUTOR",
                                "labels": {"nodes": [{"name": "enhancement"}, {"name": "feature:sessions"}]},
                                "milestone": {"title": "v1"},
                                "comments": {"totalCount": 3},
                            }
                        }
                    }
                }
            },
        }
        work_items, events, comments, reviews = extract_rows_from_record(record, max_body_chars=100, max_item_body_chars=40)
        self.assertEqual(len(work_items), 1)
        self.assertEqual(events, [])
        self.assertEqual(comments, [])
        self.assertEqual(reviews, [])
        wi = work_items[0]
        self.assertEqual(wi["repo_full_name"], "openai/openai-agents-python")
        self.assertEqual(wi["number"], 2206)
        self.assertEqual(wi["type"], "issue")
        self.assertEqual(wi["author_login"], "@alice")
        self.assertIn("feature:sessions", wi["labels_json"])
        self.assertTrue(wi["body_excerpt"].endswith("…"))

    def test_extract_timeline_labeled_event(self) -> None:
        record = {
            "request": {"body": {"variables": {"owner": "openai", "name": "openai-agents-python", "number": 1}}},
            "meta": {"tag": "graphql_timeline_item1_pstart"},
            "response": {
                "json": {
                    "data": {
                        "repository": {
                            "issueOrPullRequest": {
                                "__typename": "Issue",
                                "timelineItems": {
                                    "nodes": [
                                        {
                                            "__typename": "LabeledEvent",
                                            "id": "EV1",
                                            "createdAt": "2026-01-10T00:00:00Z",
                                            "actor": {"login": "maintainer"},
                                            "label": {"name": "bug"},
                                        }
                                    ]
                                },
                            }
                        }
                    }
                }
            },
        }
        work_items, events, comments, reviews = extract_rows_from_record(record, max_body_chars=100, max_item_body_chars=100)
        self.assertEqual(work_items, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "LabeledEvent")
        self.assertEqual(events[0]["subject_type"], "label")
        self.assertEqual(events[0]["subject"], "bug")
        self.assertEqual(events[0]["actor_login"], "@maintainer")
        self.assertEqual(comments, [])
        self.assertEqual(reviews, [])

    def test_extract_comments_excerpts(self) -> None:
        record = {
            "request": {"body": {"variables": {"owner": "openai", "name": "openai-agents-python", "number": 2}}},
            "meta": {"tag": "graphql_comments_item2_pstart"},
            "response": {
                "json": {
                    "data": {
                        "repository": {
                            "issueOrPullRequest": {
                                "__typename": "PullRequest",
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "C1",
                                            "url": "https://github.com/openai/openai-agents-python/pull/2#issuecomment-1",
                                            "body": "hello " * 50,
                                            "createdAt": "2026-01-10T00:00:00Z",
                                            "author": {"login": "bob"},
                                            "authorAssociation": "CONTRIBUTOR",
                                        }
                                    ]
                                },
                            }
                        }
                    }
                }
            },
        }
        _work_items, _events, comments, _reviews = extract_rows_from_record(record, max_body_chars=20, max_item_body_chars=100)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["author_login"], "@bob")
        self.assertTrue(comments[0]["body_excerpt"].endswith("…"))

    def test_extract_reviews(self) -> None:
        record = {
            "request": {"body": {"variables": {"owner": "openai", "name": "openai-agents-python", "number": 3}}},
            "meta": {"tag": "graphql_reviews_pr3_pstart"},
            "response": {
                "json": {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviews": {
                                    "nodes": [
                                        {
                                            "id": "R1",
                                            "author": {"login": "reviewer"},
                                            "state": "APPROVED",
                                            "body": "Looks good!",
                                            "submittedAt": "2026-01-10T00:00:00Z",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            },
        }
        _work_items, _events, _comments, reviews = extract_rows_from_record(record, max_body_chars=100, max_item_body_chars=100)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["review_state"], "APPROVED")
        self.assertEqual(reviews[0]["author_login"], "@reviewer")
