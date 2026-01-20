from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from prism.redaction.guard import (
    RedactionPolicy,
    assert_no_sensitive_data,
    load_redaction_policy,
)


class StorageError(RuntimeError):
    pass


class NotFoundError(StorageError):
    pass


class InvalidStateError(StorageError):
    pass


def _uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(value)


def _new_uuid() -> UUID:
    return uuid.uuid4()


def _vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(str(float(v)) for v in values) + "]"


@dataclass(frozen=True)
class PostgresStorage:
    database_url: str
    redaction_policy: RedactionPolicy

    @classmethod
    def from_env(
        cls,
        *,
        database_url_env: str = "DATABASE_URL",
        redaction_policy_path_env: str = "REDACTION_POLICY_PATH",
        default_redaction_policy_path: str = "phase3/redaction-policy.default.json",
    ) -> "PostgresStorage":
        database_url = os.environ.get(database_url_env)
        if not database_url:
            raise StorageError(f"Missing {database_url_env}.")
        policy_path = os.environ.get(
            redaction_policy_path_env, default_redaction_policy_path
        )
        return cls(
            database_url=database_url,
            redaction_policy=load_redaction_policy(policy_path),
        )

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.database_url)

    def create_case(
        self,
        *,
        source: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
        redaction_policy_version: str | None = None,
    ) -> UUID:
        assert_no_sensitive_data(source, policy=self.redaction_policy)
        assert_no_sensitive_data(metadata, policy=self.redaction_policy)

        metadata = metadata or {}
        case_id = _new_uuid()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cases (id, source, metadata, redaction_policy_version)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    case_id,
                    Jsonb(dict(source)),
                    Jsonb(dict(metadata)),
                    redaction_policy_version,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            return row[0]

    def append_case_events(
        self, *, case_id: str | UUID, events: Sequence[Mapping[str, Any]]
    ) -> None:
        cid = _uuid(case_id)

        rows: list[tuple[Any, ...]] = []
        for event in events:
            if "event_type" not in event or not event["event_type"]:
                raise StorageError("case_events[] requires event_type.")
            assert_no_sensitive_data(event, policy=self.redaction_policy)

            raw_event_id = event.get("id")
            event_id = _uuid(raw_event_id) if raw_event_id is not None else _new_uuid()
            rows.append(
                (
                    event_id,
                    cid,
                    event.get("court_run_id"),
                    event.get("ts"),
                    event.get("seq"),
                    event.get("actor_type"),
                    event.get("actor_id"),
                    event.get("role"),
                    event["event_type"],
                    event.get("content"),
                    Jsonb(event.get("meta") or {}),
                    Jsonb(event.get("usage"))
                    if event.get("usage") is not None
                    else None,
                )
            )

        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO case_events (
                  id,
                  case_id,
                  court_run_id,
                  ts,
                  seq,
                  actor_type,
                  actor_id,
                  role,
                  event_type,
                  content,
                  meta,
                  usage
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                rows,
            )

    def create_court_run(
        self,
        *,
        case_id: str | UUID,
        model: str | None,
        started_at: datetime | str,
    ) -> UUID:
        cid = _uuid(case_id)
        with self._connect() as conn, conn.cursor() as cur:
            court_run_id = _new_uuid()
            cur.execute(
                """
                INSERT INTO court_runs (id, case_id, model, started_at, status)
                VALUES (%s, %s, %s, %s, 'running')
                RETURNING id;
                """,
                (court_run_id, cid, model, started_at),
            )
            row = cur.fetchone()
            assert row is not None
            return row[0]

    def finish_court_run(
        self,
        *,
        court_run_id: str | UUID,
        status: str,
        artifacts_redacted: Mapping[str, Any] | None,
    ) -> None:
        rid = _uuid(court_run_id)
        assert_no_sensitive_data(artifacts_redacted, policy=self.redaction_policy)

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE court_runs
                SET ended_at = now(),
                    status = %s,
                    artifacts = %s
                WHERE id = %s;
                """,
                (
                    status,
                    Jsonb(artifacts_redacted)
                    if artifacts_redacted is not None
                    else None,
                    rid,
                ),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"court_run not found: {rid}")

    def store_judgement(
        self,
        *,
        case_id: str | UUID,
        court_run_id: str | UUID | None,
        decision_json: Mapping[str, Any],
    ) -> UUID:
        cid = _uuid(case_id)
        rid = _uuid(court_run_id) if court_run_id is not None else None
        assert_no_sensitive_data(decision_json, policy=self.redaction_policy)

        with self._connect() as conn, conn.cursor() as cur:
            judgement_id = _new_uuid()
            cur.execute(
                """
                INSERT INTO judgements (id, case_id, court_run_id, decision)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (judgement_id, cid, rid, Jsonb(dict(decision_json))),
            )
            row = cur.fetchone()
            assert row is not None
            return row[0]

    @cached_property
    def _lessons_embedding_udt_name(self) -> str | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_name = 'lessons' AND column_name = 'embedding';
                """
            )
            row = cur.fetchone()
            return row[0] if row else None

    def store_lessons(
        self, *, case_id: str | UUID, lessons: Sequence[Mapping[str, Any]]
    ) -> None:
        cid = _uuid(case_id)

        embedding_udt = self._lessons_embedding_udt_name

        rows: list[tuple[Any, ...]] = []
        for lesson in lessons:
            if not lesson.get("role"):
                raise StorageError("lessons[] requires role.")
            if not lesson.get("content"):
                raise StorageError("lessons[] requires content.")
            assert_no_sensitive_data(lesson, policy=self.redaction_policy)

            embedding_value = lesson.get("embedding")
            if embedding_value is None:
                embedding_param = None
            else:
                if embedding_udt == "vector":
                    embedding_param = _vector_literal(embedding_value)
                else:
                    embedding_param = list(embedding_value)

            lesson_id = _new_uuid()
            rows.append(
                (
                    lesson_id,
                    cid,
                    lesson["role"],
                    lesson.get("polarity"),
                    lesson.get("title"),
                    lesson["content"],
                    lesson.get("rationale"),
                    lesson.get("confidence"),
                    lesson.get("tags"),
                    lesson.get("evidence_event_ids"),
                    embedding_param,
                    lesson.get("embedding_model"),
                    lesson.get("embedding_dim"),
                    lesson.get("supersedes_lesson_id"),
                )
            )

        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO lessons (
                  id,
                  case_id,
                  role,
                  polarity,
                  title,
                  content,
                  rationale,
                  confidence,
                  tags,
                  evidence_event_ids,
                  embedding,
                  embedding_model,
                  embedding_dim,
                  supersedes_lesson_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                rows,
            )

    def store_prompt_update(
        self,
        *,
        case_id: str | UUID | None,
        agent_id: str | None,
        role: str,
        from_version: int | None,
        proposal: str,
        reason: str | None,
    ) -> UUID:
        cid = _uuid(case_id) if case_id is not None else None
        assert_no_sensitive_data(
            {
                "agent_id": agent_id,
                "role": role,
                "proposal": proposal,
                "reason": reason,
            },
            policy=self.redaction_policy,
        )

        with self._connect() as conn, conn.cursor() as cur:
            prompt_update_id = _new_uuid()
            cur.execute(
                """
                INSERT INTO prompt_updates (id, case_id, agent_id, role, from_version, proposal, reason, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'proposed')
                RETURNING id;
                """,
                (prompt_update_id, cid, agent_id, role, from_version, proposal, reason),
            )
            row = cur.fetchone()
            assert row is not None
            return row[0]

    def review_prompt_update(
        self,
        *,
        prompt_update_id: str | UUID,
        status: str,
        review_comment: str | None,
        approved_by: str | None,
    ) -> None:
        pid = _uuid(prompt_update_id)
        if status not in {"approved", "rejected"}:
            raise StorageError("review_prompt_update status must be approved|rejected.")
        assert_no_sensitive_data(
            {"review_comment": review_comment, "approved_by": approved_by},
            policy=self.redaction_policy,
        )

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE prompt_updates
                SET status = %s,
                    review_comment = %s,
                    approved_by = %s,
                    approved_at = CASE WHEN %s = 'approved' THEN now() ELSE NULL END
                WHERE id = %s;
                """,
                (status, review_comment, approved_by, status, pid),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"prompt_update not found: {pid}")

    def apply_prompt_update(self, *, prompt_update_id: str | UUID) -> int:
        pid = _uuid(prompt_update_id)
        with self._connect() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, proposal, status
                    FROM prompt_updates
                    WHERE id = %s
                    FOR UPDATE;
                    """,
                    (pid,),
                )
                row = cur.fetchone()
                if row is None:
                    raise NotFoundError(f"prompt_update not found: {pid}")

                role, proposal, status = row
                if status != "approved":
                    raise InvalidStateError(
                        f"prompt_update must be approved before apply (id={pid}, status={status})."
                    )

                cur.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM role_prompts WHERE role = %s;",
                    (role,),
                )
                max_version_row = cur.fetchone()
                assert max_version_row is not None
                new_version = int(max_version_row[0]) + 1

                role_prompt_id = _new_uuid()
                cur.execute(
                    """
                    INSERT INTO role_prompts (id, role, version, prompt, is_active)
                    VALUES (%s, %s, %s, %s, true)
                    RETURNING id;
                    """,
                    (role_prompt_id, role, new_version, proposal),
                )
                new_prompt_id_row = cur.fetchone()
                assert new_prompt_id_row is not None
                new_prompt_id = new_prompt_id_row[0]

                cur.execute(
                    """
                    UPDATE role_prompts
                    SET is_active = false
                    WHERE role = %s AND id <> %s AND is_active = true;
                    """,
                    (role, new_prompt_id),
                )

                cur.execute(
                    """
                    UPDATE prompt_updates
                    SET status = 'applied',
                        applied_at = now()
                    WHERE id = %s;
                    """,
                    (pid,),
                )
                return new_version


def default_migrations_dir() -> Path:
    return Path(__file__).with_suffix("").parent / "migrations"
