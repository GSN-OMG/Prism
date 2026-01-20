from __future__ import annotations

from prism.redaction.guard import (
    UnredactedDataError,
    assert_no_sensitive_data,
    load_redaction_policy,
)


def test_guard_detects_openai_key_like() -> None:
    policy = load_redaction_policy("redaction-policy.default.json")
    payload = {"msg": "my key is sk-proj-abcdefghijklmnopqrstuvwx1234567890"}
    try:
        assert_no_sensitive_data(payload, policy=policy)
    except UnredactedDataError as e:
        assert e.rule_name == "openai_api_key_like"
        assert e.json_path == "$.msg"
    else:
        raise AssertionError("Expected UnredactedDataError")


def test_guard_detects_nested_email() -> None:
    policy = load_redaction_policy("redaction-policy.default.json")
    payload = {"events": [{"content": "contact me at test@example.com"}]}
    try:
        assert_no_sensitive_data(payload, policy=policy)
    except UnredactedDataError as e:
        assert e.rule_name == "email"
        assert e.json_path == "$.events[0].content"
    else:
        raise AssertionError("Expected UnredactedDataError")


def test_guard_allows_redacted_placeholder() -> None:
    policy = load_redaction_policy("redaction-policy.default.json")
    payload = {"msg": "token=***REDACTED:secret***"}
    assert_no_sensitive_data(payload, policy=policy)
