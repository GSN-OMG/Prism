from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devrel.agents.types import Contributor, Issue


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures"


def load_json(relative_path: str) -> Any:
    path = fixtures_dir() / relative_path
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def issue_from_github_json(payload: dict[str, Any]) -> Issue:
    labels = tuple(label.get("name", "") for label in payload.get("labels", []) if label.get("name"))
    return Issue(
        number=int(payload["number"]),
        title=str(payload.get("title", "")),
        body=str(payload.get("body", "") or ""),
        labels=labels,
    )


def contributor_from_profile_json(payload: dict[str, Any]) -> Contributor:
    return Contributor(
        login=str(payload["login"]),
        areas=tuple(payload.get("areas", []) or []),
        recent_activity_score=float(payload.get("recent_activity_score", 0.0)),
        merged_prs=int(payload.get("merged_prs", 0)),
        reviews=int(payload.get("reviews", 0)),
    )

