from __future__ import annotations

from pathlib import Path

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

