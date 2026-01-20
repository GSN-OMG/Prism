from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.helpers.dotenv import load_dotenv


def pytest_configure() -> None:
    tests_dir = Path(__file__).resolve().parent
    project_root = tests_dir.parent  # phase2/prism-devrel
    phase2_root = project_root.parent  # phase2/
    repo_root = phase2_root.parent  # repo root

    load_dotenv(
        repo_root / ".env",
        phase2_root / ".env",
        project_root / ".env",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    _ = config
    if os.getenv("OPENAI_API_KEY"):
        return
    skip = pytest.mark.skip(reason="OPENAI_API_KEY not set (live LLM tests skipped).")
    for item in items:
        if "llm_judge" in item.keywords or "llm_live" in item.keywords:
            item.add_marker(skip)
