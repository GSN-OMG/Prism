from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(*, path: str | Path = ".env", override: bool = False) -> bool:
    """
    Load a local .env file into os.environ.

    - Intended for local development only (the .env file should be gitignored).
    - Does not log any values.
    - Parsing is intentionally minimal; keep your .env simple (KEY=value).
    """
    env_path = Path(path)
    if not env_path.exists():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and (
            (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
        ):
            value = value[1:-1]

        if not override and key in os.environ:
            continue
        os.environ[key] = value

    return True
