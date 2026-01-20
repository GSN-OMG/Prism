from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

RedactionAction = Literal["mask", "partial", "hash", "drop"]


@dataclass(frozen=True, slots=True)
class RedactionRule:
    name: str
    category: str
    action: RedactionAction
    pattern: str
    replacement: str | None = None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RedactionPolicy:
    version: str
    rules: tuple[RedactionRule, ...]
    description: str | None = None


def load_redaction_policy(path: str | Path) -> RedactionPolicy:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rules: list[RedactionRule] = []
    for raw_rule in data["rules"]:
        rules.append(
            RedactionRule(
                name=raw_rule["name"],
                category=raw_rule["category"],
                action=raw_rule["action"],
                pattern=raw_rule["pattern"],
                replacement=raw_rule.get("replacement"),
                enabled=raw_rule.get("enabled", True),
            )
        )
    return RedactionPolicy(
        version=data["version"],
        description=data.get("description"),
        rules=tuple(rules),
    )


class Redactor:
    def __init__(
        self,
        policy: RedactionPolicy,
        *,
        keep_start: int = 4,
        keep_end: int = 4,
    ) -> None:
        self._policy = policy
        self._keep_start = keep_start
        self._keep_end = keep_end

        compiled: list[tuple[RedactionRule, re.Pattern[str]]] = []
        for rule in policy.rules:
            if not rule.enabled:
                continue
            compiled.append((rule, re.compile(rule.pattern)))
        self._compiled = tuple(compiled)

    @property
    def policy_version(self) -> str:
        return self._policy.version

    def redact(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return self._redact_str(value)
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items()}
        return value

    def _redact_str(self, text: str) -> str:
        out = text
        for rule, pattern in self._compiled:
            out = pattern.sub(lambda m: self._replacement(rule, m.group(0)), out)
        return out

    def _replacement(self, rule: RedactionRule, matched: str) -> str:
        if rule.replacement is not None:
            return rule.replacement

        if rule.action == "mask":
            return f"***REDACTED:{rule.category}***"
        if rule.action == "drop":
            return f"***REDACTED:{rule.category}:DROPPED***"
        if rule.action == "partial":
            if len(matched) <= (self._keep_start + self._keep_end + 4):
                return f"***REDACTED:{rule.category}***"
            return (
                matched[: self._keep_start]
                + f"***REDACTED:{rule.category}***"
                + matched[-self._keep_end :]
            )
        if rule.action == "hash":
            # Not recommended for MVP; treat as mask by default.
            return f"***REDACTED:{rule.category}***"

        return f"***REDACTED:{rule.category}***"
