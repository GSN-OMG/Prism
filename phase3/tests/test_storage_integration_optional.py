from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from prism.storage.migrate import run_migrations
from prism.storage.postgres import PostgresStorage, default_migrations_dir


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL")
def test_storage_rejects_unredacted_event_and_accepts_redacted_event() -> None:
    storage = PostgresStorage.from_env()
    run_migrations(
        database_url=storage.database_url, migrations_dir=default_migrations_dir()
    )

    case_id = storage.create_case(
        source={"system": "test", "kind": "integration"},
        metadata={"note": "all redacted"},
        redaction_policy_version=storage.redaction_policy.version,
    )

    with pytest.raises(ValueError):
        storage.append_case_events(
            case_id=case_id,
            events=[
                {
                    "event_type": "note",
                    "content": "leak sk-proj-abcdefghijklmnopqrstuvwx1234567890",
                }
            ],
        )

    storage.append_case_events(
        case_id=case_id,
        events=[
            {
                "event_type": "note",
                "ts": datetime.now(timezone.utc).isoformat(),
                "content": "ok ***REDACTED:secret***",
                "meta": {"k": "v"},
            }
        ],
    )
