import json
import unittest

from prism.phase3.court_orchestrator import CourtOrchestrator
from prism.phase3.models import CaseEvent
from prism.phase3.redaction import Redactor, load_redaction_policy
from prism.phase3.storage import InMemoryStorage


class FakeAgentRunner:
    def __init__(self, *, fail_stages: set[str] | None = None) -> None:
        self.fail_stages = fail_stages or set()
        self.inputs: dict[str, dict] = {}

    async def run(self, *, stage: str, input: dict, tools):  # noqa: ANN001
        self.inputs[stage] = input
        if stage in self.fail_stages:
            raise RuntimeError(f"boom:{stage}")

        evidence = []
        if isinstance(input.get("events"), list) and input["events"]:
            evidence = [input["events"][0]["id"]]

        if stage == "prosecutor":
            return {
                "output": {
                    "criticisms": ["Too many retries without backoff."],
                    "candidate_lessons": [
                        {
                            "role": "coder",
                            "polarity": "dont",
                            "title": "Do not leak secrets",
                            "content": (
                                "Never paste API keys like sk-proj-1234567890abcdef1234567890 into logs."
                            ),
                            "rationale": "Leaks cause account compromise.",
                            "confidence": 0.8,
                            "tags": ["security"],
                            "evidence_event_ids": evidence,
                        }
                    ],
                },
                "usage": {"input_tokens": 12, "output_tokens": 34},
            }

        if stage == "defense":
            return {
                "output": {
                    "praises": ["Good use of structured outputs."],
                    "candidate_lessons": [],
                },
                "usage": {"input_tokens": 10, "output_tokens": 10},
            }

        if stage == "jury":
            return {
                "output": {
                    "observations": ["The timeline has enough evidence events."],
                    "risks": ["Some stages may fail; judge should proceed."],
                    "missing_info": [],
                    "candidate_lessons": [],
                },
                "usage": {"input_tokens": 11, "output_tokens": 9},
            }

        if stage == "judge":
            return {
                "output": {
                    "selected_lessons": [
                        {
                            "role": "coder",
                            "polarity": "dont",
                            "title": "Do not leak secrets",
                            "content": "Never include API keys in logs or issues.",
                            "rationale": "Prevent credential compromise.",
                            "confidence": 0.9,
                            "tags": ["security"],
                            "evidence_event_ids": evidence,
                        }
                    ],
                    "deferred_lessons": [],
                    "prompt_update_proposals": [
                        {
                            "role": "coder",
                            "agent_id": "agent-1",
                            "from_version": "v1",
                            "proposal": (
                                "SYSTEM: Never log secrets like sk-proj-1234567890abcdef1234567890."
                            ),
                            "reason": "Reduce accidental secret leakage.",
                            "evidence_event_ids": evidence,
                        }
                    ],
                    "user_improvement_suggestions": [],
                    "system_improvement_suggestions": [],
                },
                "usage": {"input_tokens": 20, "output_tokens": 40},
            }

        raise AssertionError(f"unexpected stage: {stage}")


class CourtOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_and_persists_artifacts_and_updates(self) -> None:
        storage = InMemoryStorage()
        redactor = Redactor(
            load_redaction_policy("phase3/redaction-policy.default.json")
        )
        agent_runner = FakeAgentRunner()
        orchestrator = CourtOrchestrator(
            storage=storage, agent_runner=agent_runner, redactor=redactor
        )

        secret = "sk-proj-1234567890abcdef1234567890"
        case_id = storage.create_case(metadata={"note": f"contains {secret}"})
        storage.append_case_events(
            case_id,
            [
                CaseEvent(
                    id="evt-1",
                    actor_type="human",
                    event_type="github.issue.comment",
                    content=f"user pasted {secret}",
                )
            ],
        )
        initial_event_count = len(storage.events[case_id])

        summary = await orchestrator.run_case(case_id=case_id, model="test-model")

        self.assertEqual(summary.case_id, case_id)
        self.assertEqual(summary.status, "completed")
        self.assertIn(summary.court_run_id, storage.court_runs)

        # Ensure the LLM inputs are redacted even if the stored events contain secrets.
        all_inputs = json.dumps(agent_runner.inputs, ensure_ascii=False)
        self.assertNotIn(secret, all_inputs)
        self.assertIn("***REDACTED:secret***", all_inputs)

        # Ensure newly stored events do not contain the full secret.
        new_events = storage.events[case_id][initial_event_count:]
        new_events_json = json.dumps(
            [e.to_dict() for e in new_events], ensure_ascii=False
        )
        self.assertNotIn(secret, new_events_json)
        self.assertIn("***REDACTED:secret***", new_events_json)

        # Ensure prompt updates are stored as proposed and redacted.
        self.assertEqual(len(storage.prompt_updates), 1)
        update = next(iter(storage.prompt_updates.values()))
        self.assertEqual(update.status, "proposed")
        self.assertNotIn(secret, update.proposal)
        self.assertIn("***REDACTED:secret***", update.proposal)

        # Ensure lessons are stored.
        self.assertEqual(len(storage.lessons), 1)

    async def test_partial_failure_still_runs_judge(self) -> None:
        storage = InMemoryStorage()
        redactor = Redactor(
            load_redaction_policy("phase3/redaction-policy.default.json")
        )
        agent_runner = FakeAgentRunner(fail_stages={"defense"})
        orchestrator = CourtOrchestrator(
            storage=storage, agent_runner=agent_runner, redactor=redactor
        )

        case_id = storage.create_case(metadata={"note": "no secrets here"})
        storage.append_case_events(
            case_id,
            [
                CaseEvent(
                    id="evt-1",
                    actor_type="human",
                    event_type="github.issue.opened",
                    content="opened",
                )
            ],
        )

        summary = await orchestrator.run_case(case_id=case_id, model="test-model")
        self.assertEqual(summary.status, "completed_with_errors")

        run = storage.court_runs[summary.court_run_id]
        self.assertEqual(run.status, "completed_with_errors")

        events = [e.to_dict() for e in storage.events[case_id]]
        self.assertTrue(any(e.get("stage") == "defense" for e in events))
        self.assertTrue(
            any(
                e.get("stage") == "defense" and e.get("event_type") == "error"
                for e in events
            )
        )

        # Judge still produces prompt update proposals.
        self.assertEqual(len(storage.prompt_updates), 1)


if __name__ == "__main__":
    unittest.main()
