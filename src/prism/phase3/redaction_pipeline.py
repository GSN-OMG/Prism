from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from prism.env import load_dotenv

RedactionAction = Literal["mask", "partial", "hash", "drop"]

_DEFAULT_KEEP_START: Final[int] = 4
_DEFAULT_KEEP_END: Final[int] = 4


@dataclass(frozen=True)
class CompiledRedactionRule:
    name: str
    category: str
    action: RedactionAction
    regex: re.Pattern[str]
    replacement: str | None = None
    enabled: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class RedactionPolicy:
    version: str
    description: str | None
    rules: tuple[CompiledRedactionRule, ...]


@dataclass
class RedactionReport:
    policy_version: str
    rule_counts: dict[str, int] = field(default_factory=dict)

    def record(self, rule_name: str, count: int) -> None:
        if count <= 0:
            return
        self.rule_counts[rule_name] = self.rule_counts.get(rule_name, 0) + count


@dataclass(frozen=True)
class RedactionResult:
    redacted: Any
    report: RedactionReport


def _find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here,) + tuple(here.parents):
        if (candidate / "phase3" / "redaction-policy.default.json").exists():
            return candidate
    raise FileNotFoundError(
        "Unable to locate repo root containing phase3/redaction-policy.default.json"
    )


def load_redaction_policy(path: str | Path) -> RedactionPolicy:
    policy_path = Path(path)
    raw = json.loads(policy_path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise ValueError("Redaction policy must be a JSON object")

    version = raw.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("Redaction policy requires non-empty string 'version'")

    description = raw.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError("Redaction policy 'description' must be a string when present")

    rules_raw = raw.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise ValueError("Redaction policy requires non-empty array 'rules'")

    compiled_rules: list[CompiledRedactionRule] = []
    for rule in rules_raw:
        if not isinstance(rule, dict):
            raise ValueError("Each rule must be an object")

        name = rule.get("name")
        category = rule.get("category")
        action = rule.get("action")
        pattern = rule.get("pattern")
        replacement = rule.get("replacement")
        enabled = rule.get("enabled", True)
        notes = rule.get("notes")

        if not isinstance(name, str) or not name:
            raise ValueError("Rule requires non-empty string 'name'")
        if not isinstance(category, str) or not category:
            raise ValueError(f"Rule {name!r} requires non-empty string 'category'")
        if action not in ("mask", "partial", "hash", "drop"):
            raise ValueError(f"Rule {name!r} has invalid action: {action!r}")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"Rule {name!r} requires non-empty string 'pattern'")
        if replacement is not None and not isinstance(replacement, str):
            raise ValueError(
                f"Rule {name!r} 'replacement' must be a string when present"
            )
        if not isinstance(enabled, bool):
            raise ValueError(f"Rule {name!r} 'enabled' must be a boolean when present")
        if notes is not None and not isinstance(notes, str):
            raise ValueError(f"Rule {name!r} 'notes' must be a string when present")

        try:
            regex = re.compile(pattern)
        except re.error as exc:  # pragma: no cover
            raise ValueError(f"Rule {name!r} has invalid regex pattern") from exc

        compiled_rules.append(
            CompiledRedactionRule(
                name=name,
                category=category,
                action=action,
                regex=regex,
                replacement=replacement,
                enabled=enabled,
                notes=notes,
            )
        )

    return RedactionPolicy(
        version=version, description=description, rules=tuple(compiled_rules)
    )


def load_default_redaction_policy() -> RedactionPolicy:
    root = _find_repo_root()
    return load_redaction_policy(root / "phase3" / "redaction-policy.default.json")


def redact_json(value: Any, *, policy: RedactionPolicy) -> RedactionResult:
    report = RedactionReport(policy_version=policy.version)
    redacted = _redact_node(value, policy=policy, report=report)
    return RedactionResult(redacted=redacted, report=report)


def _placeholder(rule: CompiledRedactionRule) -> str:
    return rule.replacement or f"***REDACTED:{rule.category}***"


def _hash_placeholder(rule: CompiledRedactionRule, token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return rule.replacement or f"***REDACTED:{rule.category}:HASH:{digest}***"


def _apply_rules(text: str, *, policy: RedactionPolicy, report: RedactionReport) -> str:
    redacted = text
    for rule in policy.rules:
        if not rule.enabled:
            continue

        if rule.action in ("mask", "drop"):
            repl = _placeholder(rule)
            redacted, count = rule.regex.subn(repl, redacted)
            report.record(rule.name, count)
            continue

        if rule.action == "partial":
            middle = _placeholder(rule)

            def repl_fn(match: re.Match[str]) -> str:
                token = match.group(0)
                if len(token) <= _DEFAULT_KEEP_START + _DEFAULT_KEEP_END:
                    return middle
                return token[:_DEFAULT_KEEP_START] + middle + token[-_DEFAULT_KEEP_END:]

            redacted, count = rule.regex.subn(repl_fn, redacted)
            report.record(rule.name, count)
            continue

        if rule.action == "hash":

            def repl_fn(match: re.Match[str]) -> str:
                return _hash_placeholder(rule, match.group(0))

            redacted, count = rule.regex.subn(repl_fn, redacted)
            report.record(rule.name, count)
            continue

        raise AssertionError(f"Unhandled action: {rule.action}")  # pragma: no cover

    return redacted


def _redact_node(
    value: Any, *, policy: RedactionPolicy, report: RedactionReport
) -> Any:
    if isinstance(value, str):
        return _apply_rules(value, policy=policy, report=report)

    if isinstance(value, list):
        return [_redact_node(item, policy=policy, report=report) for item in value]

    if isinstance(value, dict):
        return {
            key: _redact_node(child, policy=policy, report=report)
            for key, child in value.items()
        }

    return value


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Redact JSON using a RedactionPolicy JSON file."
    )
    parser.add_argument(
        "--policy",
        type=str,
        default=os.environ.get(
            "REDACTION_POLICY_PATH",
            str(_find_repo_root() / "phase3" / "redaction-policy.default.json"),
        ),
        help="Path to redaction policy JSON file",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Emit a redaction report to stderr (counts only; no original text).",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input JSON file (default: '-' for stdin)",
    )
    args = parser.parse_args(argv)

    policy = load_redaction_policy(args.policy)

    if args.input == "-":
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))

    result = redact_json(payload, policy=policy)
    json.dump(result.redacted, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")

    if args.report:
        json.dump(
            {
                "policy_version": result.report.policy_version,
                "rule_counts": result.report.rule_counts,
            },
            sys.stderr,
            ensure_ascii=False,
            indent=2,
        )
        sys.stderr.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
