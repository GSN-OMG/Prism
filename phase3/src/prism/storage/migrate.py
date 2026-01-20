from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg

from prism.env import load_dotenv


@dataclass(frozen=True)
class Migration:
    filename: str
    sql: str


def _load_migrations(migrations_dir: Path) -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        migrations.append(
            Migration(filename=path.name, sql=path.read_text(encoding="utf-8"))
        )
    return migrations


def run_migrations(*, database_url: str, migrations_dir: Path) -> None:
    migrations = _load_migrations(migrations_dir)
    if not migrations:
        return

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  filename text PRIMARY KEY,
                  applied_at timestamptz NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute("SELECT filename FROM schema_migrations;")
            applied = {row[0] for row in cur.fetchall()}

        for migration in migrations:
            if migration.filename in applied:
                continue
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(migration.sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s);",
                        (migration.filename,),
                    )


def main() -> None:
    load_dotenv()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Missing DATABASE_URL.")
    migrations_dir = Path(__file__).with_suffix("").parent / "migrations"
    run_migrations(database_url=database_url, migrations_dir=migrations_dir)


if __name__ == "__main__":
    main()
