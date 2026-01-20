from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from functools import cache
from typing import Sequence

import psycopg

from prism.db import connect
from prism.embeddings import (
    Embedder,
    EmbeddingResult,
    compose_lesson_embedding_text,
    embed_text,
)


def vector_literal(vector: Sequence[float]) -> str:
    parts: list[str] = []
    for value in vector:
        float_value = float(value)
        if not math.isfinite(float_value):
            raise ValueError("Vector contains non-finite float.")
        parts.append(repr(float_value))
    return "[" + ",".join(parts) + "]"


LESSONS_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS lessons (
  id UUID PRIMARY KEY,
  case_id UUID NULL,
  role TEXT NOT NULL,
  polarity TEXT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  rationale TEXT NOT NULL,
  confidence REAL NULL,
  tags TEXT[] NULL,
  evidence_event_ids UUID[] NULL,
  embedding vector NULL,
  embedding_model TEXT NULL,
  embedding_dim INT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  supersedes_lesson_id UUID NULL
);

CREATE INDEX IF NOT EXISTS lessons_role_idx ON lessons(role);
"""


@dataclass(frozen=True)
class LessonInput:
    role: str
    title: str
    content: str
    rationale: str
    case_id: str | None = None
    polarity: str | None = None
    confidence: float | None = None
    tags: list[str] | None = None
    evidence_event_ids: list[str] | None = None
    supersedes_lesson_id: str | None = None


@dataclass(frozen=True)
class LessonRecord(LessonInput):
    id: str = ""
    embedding_model: str | None = None
    embedding_dim: int | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class LessonSearchHit:
    lesson: LessonRecord
    distance: float


@cache
def _redaction_policy_from_env():
    import os

    from prism.redaction.guard import load_redaction_policy

    path = os.environ.get(
        "REDACTION_POLICY_PATH", "phase3/redaction-policy.default.json"
    )
    return load_redaction_policy(path)


def _assert_no_sensitive_data(value: object) -> None:
    from prism.redaction.guard import assert_no_sensitive_data

    assert_no_sensitive_data(value, policy=_redaction_policy_from_env())


def _lessons_embedding_udt_name(conn: psycopg.Connection) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_name = 'lessons' AND column_name = 'embedding';
            """
        )
        row = cur.fetchone()
        return row[0] if row else None


def _require_pgvector(conn: psycopg.Connection) -> None:
    udt = _lessons_embedding_udt_name(conn)
    if udt != "vector":
        raise RuntimeError(
            "pgvector is required for embeddings search. "
            "Install the `vector` extension and re-run migrations."
        )


def ensure_lessons_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(LESSONS_SCHEMA_SQL)


def ensure_lessons_vector_index(
    conn: psycopg.Connection,
    *,
    index_method: str = "hnsw",
    operator_class: str = "vector_l2_ops",
    index_name: str = "lessons_embedding_ann_idx",
) -> None:
    from psycopg import sql

    allowed_index_methods = {"hnsw", "ivfflat"}
    allowed_operator_classes = {"vector_l2_ops", "vector_cosine_ops", "vector_ip_ops"}

    if index_method not in allowed_index_methods:
        raise ValueError(f"Unsupported index_method: {index_method!r}")
    if operator_class not in allowed_operator_classes:
        raise ValueError(f"Unsupported operator_class: {operator_class!r}")

    _require_pgvector(conn)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "CREATE INDEX IF NOT EXISTS {} ON lessons USING {} (embedding {});"
            ).format(
                sql.Identifier(index_name),
                sql.SQL(index_method),
                sql.SQL(operator_class),
            )
        )


def _lesson_text_for_embedding(lesson: LessonInput) -> str:
    return compose_lesson_embedding_text(
        title=lesson.title,
        content=lesson.content,
        rationale=lesson.rationale,
    )


def _new_lesson_id() -> str:
    return str(uuid.uuid4())


def store_lesson_with_embedding(
    conn: psycopg.Connection,
    *,
    lesson: LessonInput,
    embedder: Embedder,
) -> tuple[str, EmbeddingResult]:
    _assert_no_sensitive_data(lesson.__dict__)
    _require_pgvector(conn)

    embedding_input = _lesson_text_for_embedding(lesson)
    embedding = embed_text(embedder=embedder, text=embedding_input)

    lesson_id = _new_lesson_id()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO lessons (
              id, case_id, role, polarity, title, content, rationale, confidence,
              tags, evidence_event_ids,
              embedding, embedding_model, embedding_dim,
              supersedes_lesson_id
            ) VALUES (
              %(id)s, %(case_id)s, %(role)s, %(polarity)s, %(title)s, %(content)s, %(rationale)s, %(confidence)s,
              %(tags)s, %(evidence_event_ids)s,
              (%(embedding)s)::vector, %(embedding_model)s, %(embedding_dim)s,
              %(supersedes_lesson_id)s
            )
            """,
            {
                "id": lesson_id,
                "case_id": lesson.case_id,
                "role": lesson.role,
                "polarity": lesson.polarity,
                "title": lesson.title,
                "content": lesson.content,
                "rationale": lesson.rationale,
                "confidence": lesson.confidence,
                "tags": lesson.tags,
                "evidence_event_ids": lesson.evidence_event_ids,
                "embedding": vector_literal(embedding.vector),
                "embedding_model": embedding.embedding_model,
                "embedding_dim": embedding.embedding_dim,
                "supersedes_lesson_id": lesson.supersedes_lesson_id,
            },
        )

    return lesson_id, embedding


def search_lessons(
    conn: psycopg.Connection,
    *,
    role: str,
    query: str,
    k: int = 5,
    embedder: Embedder,
    require_same_model: bool = True,
) -> list[LessonSearchHit]:
    if k <= 0:
        raise ValueError("k must be positive.")

    _assert_no_sensitive_data({"role": role, "query": query})
    _require_pgvector(conn)

    query_embedding = embed_text(embedder=embedder, text=query)
    query_vector = vector_literal(query_embedding.vector)

    filters = ["role = %(role)s", "embedding IS NOT NULL"]
    params: dict[str, object] = {"role": role, "k": k, "query_vector": query_vector}

    if require_same_model:
        filters.append("embedding_model = %(embedding_model)s")
        filters.append("embedding_dim = %(embedding_dim)s")
        params["embedding_model"] = query_embedding.embedding_model
        params["embedding_dim"] = query_embedding.embedding_dim

    sql = f"""
        SELECT
          id, case_id, role, polarity, title, content, rationale, confidence,
          tags, evidence_event_ids,
          embedding_model, embedding_dim, created_at, supersedes_lesson_id,
          embedding <-> (%(query_vector)s)::vector AS distance
        FROM lessons
        WHERE {" AND ".join(filters)}
        ORDER BY embedding <-> (%(query_vector)s)::vector
        LIMIT %(k)s
    """

    hits: list[LessonSearchHit] = []
    with conn.cursor() as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            (
                lesson_id,
                case_id,
                row_role,
                polarity,
                title,
                content,
                rationale,
                confidence,
                tags,
                evidence_event_ids,
                embedding_model,
                embedding_dim,
                created_at,
                supersedes_lesson_id,
                distance,
            ) = row

            record = LessonRecord(
                id=str(lesson_id),
                case_id=str(case_id) if case_id is not None else None,
                role=row_role,
                polarity=polarity,
                title=title,
                content=content,
                rationale=rationale,
                confidence=confidence,
                tags=list(tags) if tags is not None else None,
                evidence_event_ids=[str(x) for x in evidence_event_ids]
                if evidence_event_ids is not None
                else None,
                embedding_model=embedding_model,
                embedding_dim=embedding_dim,
                created_at=created_at.isoformat() if created_at is not None else None,
                supersedes_lesson_id=str(supersedes_lesson_id)
                if supersedes_lesson_id is not None
                else None,
            )
            hits.append(LessonSearchHit(lesson=record, distance=float(distance)))

    return hits


def find_duplicate_candidates(
    conn: psycopg.Connection,
    *,
    lesson: LessonInput,
    embedder: Embedder,
    k: int = 5,
    max_distance: float = 0.25,
) -> list[LessonSearchHit]:
    embedding_input = _lesson_text_for_embedding(lesson)
    hits = search_lessons(
        conn, role=lesson.role, query=embedding_input, k=k, embedder=embedder
    )
    return [hit for hit in hits if hit.distance <= max_distance]


def search_lessons_from_env(
    *, role: str, query: str, k: int = 5
) -> list[LessonSearchHit]:
    import os

    from prism.embeddings import Model2VecEmbedder
    from prism.storage.migrate import run_migrations
    from prism.storage.postgres import default_migrations_dir

    embedder = Model2VecEmbedder.from_env()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Missing `DATABASE_URL` env var.")

    run_migrations(database_url=database_url, migrations_dir=default_migrations_dir())
    with connect(db_url=database_url) as conn:
        return search_lessons(conn, role=role, query=query, k=k, embedder=embedder)


def main() -> None:
    import argparse
    import json
    from dataclasses import asdict

    parser = argparse.ArgumentParser(prog="prism.phase3.embeddings_and_search")
    sub = parser.add_subparsers(dest="cmd", required=True)

    search = sub.add_parser(
        "search-lessons", help="Search lessons by embedding similarity (Top-K)."
    )
    search.add_argument("--role", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--k", type=int, default=5)

    index = sub.add_parser(
        "create-index", help="Create pgvector ANN index on lessons.embedding."
    )
    index.add_argument("--index-method", default="hnsw", choices=["hnsw", "ivfflat"])
    index.add_argument(
        "--operator-class",
        default="vector_l2_ops",
        choices=["vector_l2_ops", "vector_cosine_ops", "vector_ip_ops"],
    )
    index.add_argument("--index-name", default="lessons_embedding_ann_idx")

    args = parser.parse_args()

    if args.cmd == "search-lessons":
        hits = search_lessons_from_env(role=args.role, query=args.query, k=args.k)
        payload = [{"distance": h.distance, "lesson": asdict(h.lesson)} for h in hits]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.cmd == "create-index":
        import os

        from prism.storage.migrate import run_migrations
        from prism.storage.postgres import default_migrations_dir

        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise SystemExit("Missing DATABASE_URL.")

        run_migrations(
            database_url=database_url, migrations_dir=default_migrations_dir()
        )
        with connect(db_url=database_url) as conn:
            ensure_lessons_vector_index(
                conn,
                index_method=args.index_method,
                operator_class=args.operator_class,
                index_name=args.index_name,
            )
        return


if __name__ == "__main__":
    main()
