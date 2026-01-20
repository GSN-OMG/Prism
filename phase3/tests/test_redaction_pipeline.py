import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


from prism.phase3.redaction_pipeline import (  # noqa: E402
    load_default_redaction_policy,
    redact_json,
)


class TestRedactionPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_default_redaction_policy()

    def test_openai_api_key_like_partial(self) -> None:
        token = "sk-proj-1234567890abcdefghijklmnopqrstuv"
        payload = {"message": f"key={token}"}

        result = redact_json(payload, policy=self.policy)

        self.assertIn("***REDACTED:secret***", result.redacted["message"])
        self.assertNotIn(token, result.redacted["message"])
        self.assertEqual(result.report.rule_counts.get("openai_api_key_like"), 1)

    def test_github_token_like_partial(self) -> None:
        token = "ghp_1234567890abcdefghijklmnopqrstuvwxYZ12"
        payload = {"token": token}

        result = redact_json(payload, policy=self.policy)

        self.assertIn("***REDACTED:secret***", result.redacted["token"])
        self.assertNotIn(token, result.redacted["token"])
        self.assertEqual(result.report.rule_counts.get("github_token_like"), 1)

    def test_bearer_token_mask_case_insensitive(self) -> None:
        payload = {"auth": "bearer abcdefghijklmnop"}

        result = redact_json(payload, policy=self.policy)

        self.assertEqual(result.redacted["auth"], "***REDACTED:secret***")
        self.assertEqual(result.report.rule_counts.get("bearer_token"), 1)

    def test_email_and_phone_mask(self) -> None:
        payload = {
            "email": "user@example.com",
            "phone": "555-123-4567",
        }

        result = redact_json(payload, policy=self.policy)

        self.assertEqual(result.redacted["email"], "***REDACTED:pii***")
        self.assertEqual(result.redacted["phone"], "***REDACTED:pii***")
        self.assertEqual(result.report.rule_counts.get("email"), 1)
        self.assertEqual(result.report.rule_counts.get("phone_like"), 1)

    def test_private_key_block_drop(self) -> None:
        private_key_block = (
            "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
        )
        payload = {"key": private_key_block}

        result = redact_json(payload, policy=self.policy)

        self.assertNotIn("BEGIN RSA PRIVATE KEY", result.redacted["key"])
        self.assertEqual(result.redacted["key"], "***REDACTED:secret***")
        self.assertEqual(result.report.rule_counts.get("private_key_block"), 1)

    def test_nested_context_bundle_fields(self) -> None:
        token = "sk-1234567890abcdefghijklmnopqrstuv"
        payload = {
            "agents": [{"id": "a1", "prompt": {"content": token}}],
            "result": {"summary": f"called with {token}"},
            "feedback": {"items": [{"note": "user@example.com"}]},
            "events": [
                {
                    "id": "e1",
                    "actor_type": "human",
                    "event_type": "demo",
                    "content": f"contact user@example.com and use {token}",
                    "meta": {"authorization": "Bearer abcdef"},
                    "usage": {"note": "555-123-4567"},
                }
            ],
        }

        result = redact_json(payload, policy=self.policy)

        self.assertIn(
            "***REDACTED:secret***", result.redacted["agents"][0]["prompt"]["content"]
        )
        self.assertIn("***REDACTED:secret***", result.redacted["result"]["summary"])
        self.assertEqual(
            result.redacted["feedback"]["items"][0]["note"], "***REDACTED:pii***"
        )
        self.assertIn("***REDACTED:pii***", result.redacted["events"][0]["content"])
        self.assertEqual(
            result.redacted["events"][0]["meta"]["authorization"],
            "***REDACTED:secret***",
        )
        self.assertEqual(
            result.redacted["events"][0]["usage"]["note"], "***REDACTED:pii***"
        )


if __name__ == "__main__":
    unittest.main()
