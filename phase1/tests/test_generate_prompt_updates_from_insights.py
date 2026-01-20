import json
import os
import tempfile
import unittest
from unittest import mock


from scripts.generate_prompt_updates_from_insights import (
    openai_chat_completion,
    render_injected_block,
)


class _FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class TestGeneratePromptUpdatesFromInsights(unittest.TestCase):
    def test_render_injected_block_includes_evidence_urls(self) -> None:
        block = render_injected_block(
            [
                {"statement": "Prefer bounded outputs.", "evidence": [{"url": "https://example.com/a"}]},
                {"statement": "Ask clarifying questions.", "evidence": [{"url": "https://example.com/b"}]},
            ],
            repo_full_name="owner/repo",
            language="en",
        )
        self.assertIn("Repo-Specific Context", block)
        self.assertIn("https://example.com/a", block)
        self.assertIn("https://example.com/b", block)

    @mock.patch("scripts.generate_prompt_updates_from_insights.urllib.request.urlopen")
    def test_openai_chat_completion_parses_content(self, m_urlopen: mock.Mock) -> None:
        payload = {"id": "resp_123", "choices": [{"message": {"content": "UPDATED PROMPT"}}]}
        m_urlopen.return_value = _FakeHTTPResponse(json.dumps(payload).encode("utf-8"))
        text, raw = openai_chat_completion(
            api_key="sk-test",
            model="gpt-test",
            system="sys",
            user="user",
            temperature=0.0,
            max_output_tokens=50,
            timeout_seconds=5.0,
        )
        self.assertEqual(text, "UPDATED PROMPT\n")
        self.assertEqual(raw.get("id"), "resp_123")

    @mock.patch("scripts.generate_prompt_updates_from_insights.openai_chat_completion")
    def test_main_writes_outputs(self, m_chat: mock.Mock) -> None:
        # Import late to avoid accidental side effects in test discovery.
        from scripts import generate_prompt_updates_from_insights as mod

        agents_md = (
            "# Agents\n\n"
            "## devrel\n"
            "Purpose: help users\n"
            "Current System Prompt:\n"
            "```text\n"
            "You are DevRel.\n"
            "```\n"
        )
        insights = {
            "repo_full_name": "owner/repo",
            "cards": [
                {"id": "c1", "statement": "Prefer concise answers.", "evidence": [{"url": "https://example.com/1"}]},
            ],
        }

        with tempfile.TemporaryDirectory() as td:
            agents_path = os.path.join(td, "AGENTS_SUMMARY.md")
            insights_path = os.path.join(td, "repo_insights.json")
            out_dir = os.path.join(td, "out_prompts")
            with open(agents_path, "w", encoding="utf-8") as f:
                f.write(agents_md)
            with open(insights_path, "w", encoding="utf-8") as f:
                json.dump(insights, f, ensure_ascii=False)

            m_chat.return_value = ("# Updated\n\nRepo-Specific Context\n- Prefer concise answers.\n", {"id": "resp_1"})

            argv = [
                "generate_prompt_updates_from_insights.py",
                "--agents-summary",
                agents_path,
                "--repo-insights",
                insights_path,
                "--out-dir",
                out_dir,
                "--language",
                "en",
            ]
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False), mock.patch("sys.argv", argv):
                rc = mod.main()
            self.assertEqual(rc, 0)

            prompt_path = os.path.join(out_dir, "devrel.system.prompt.md")
            changes_path = os.path.join(out_dir, "devrel.changes.json")
            self.assertTrue(os.path.isfile(prompt_path))
            self.assertTrue(os.path.isfile(changes_path))

            with open(prompt_path, "r", encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Repo-Specific Context", text)
            self.assertIn("Prefer concise answers.", text)

            with open(changes_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertEqual(payload.get("generation_mode"), "openai_chat_completions")
            self.assertEqual((payload.get("llm") or {}).get("response_id"), "resp_1")
