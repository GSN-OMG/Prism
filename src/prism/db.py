from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class DatabaseConfig:
    url: str


def load_database_config(env: dict[str, str] | None = None) -> DatabaseConfig:
    if env is None:
        env = os.environ

    url = env.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Missing `DATABASE_URL` env var.")

    return DatabaseConfig(url=url)


def connect(*, db_url: str | None = None) -> psycopg.Connection:
    if db_url is None:
        db_url = load_database_config().url

    return psycopg.connect(db_url, autocommit=True)
