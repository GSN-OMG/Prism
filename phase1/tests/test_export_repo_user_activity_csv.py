import datetime as dt
import unittest


from scripts.export_repo_user_activity_csv import actor_key, pick_latest_roles


class TestExportRepoUserActivityCsv(unittest.TestCase):
    def test_actor_key_prefers_login(self) -> None:
        self.assertEqual(actor_key({"login": "seratch", "id": 19658, "node_id": "MDQ6..."}), "@seratch")

    def test_pick_latest_roles_prefers_newer_observation(self) -> None:
        repo = "openai/openai-agents-python"
        user_id = "U_123"
        roles = [
            (repo, user_id, "CONTRIBUTOR", dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)),
            (repo, user_id, "MEMBER", dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)),
            (repo, user_id, "OWNER", dt.datetime(2025, 12, 31, tzinfo=dt.timezone.utc)),
        ]
        latest = pick_latest_roles(roles)
        self.assertEqual(latest[(repo, user_id)], "MEMBER")
