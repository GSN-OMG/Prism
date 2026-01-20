from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class UnredactedDataError(ValueError):
    def __init__(self, *, rule_name: str, json_path: str):
        super().__init__(
            f"Unredacted data detected (rule={rule_name}, path={json_path})."
        )
        self.rule_name = rule_name
        self.json_path = json_path


@dataclass(frozen=True)
class RedactionRule:
    name: str
    category: str
    action: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class RedactionPolicy:
    version: str
    description: str
    rules: tuple[RedactionRule, ...]


def load_redaction_policy(path: str | Path) -> RedactionPolicy:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rules: list[RedactionRule] = []
    for rule in raw.get("rules", []):
        rules.append(
            RedactionRule(
                name=str(rule["name"]),
                category=str(rule.get("category", "")),
                action=str(rule.get("action", "")),
                pattern=re.compile(str(rule["pattern"])),
            )
        )
    return RedactionPolicy(
        version=str(raw.get("version", "")),
        description=str(raw.get("description", "")),
        rules=tuple(rules),
    )


def _iter_strings(value: Any, *, path: str) -> Iterable[tuple[str, str]]:
    if value is None:
        return
    if isinstance(value, str):
        yield (path, value)
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from _iter_strings(child, path=child_path)
        return
    if isinstance(value, (list, tuple)):
        for idx, child in enumerate(value):
            child_path = f"{path}[{idx}]"
            yield from _iter_strings(child, path=child_path)


def assert_no_sensitive_data(value: Any, *, policy: RedactionPolicy) -> None:
    for json_path, text in _iter_strings(value, path="$"):
        for rule in policy.rules:
            if rule.pattern.search(text):
                raise UnredactedDataError(rule_name=rule.name, json_path=json_path)
