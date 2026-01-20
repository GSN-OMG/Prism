from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.dotenv import load_dotenv


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--llm-judge",
        action="store_true",
        default=False,
        help="Enable LLM-as-a-judge tests (will call OpenAI if configured).",
    )


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
    if config.getoption("--llm-judge"):
        return
    skip = pytest.mark.skip(reason="LLM judge disabled (use --llm-judge to enable).")
    for item in items:
        if "llm_judge" in item.keywords:
            item.add_marker(skip)
