"""RAG client for pgvector-based knowledge base search."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import psycopg
from openai import OpenAI


@dataclass(frozen=True, slots=True)
class KBDocument:
    """A document from the knowledge base."""

    kb_id: str
    item_type: str
    item_number: int
    section: str
    source_ref: str
    text: str
    metadata: dict[str, Any]
    score: float | None = None


class RAGClient:
    """Client for searching the phase1 pgvector knowledge base."""

    def __init__(
        self,
        *,
        db_host: str | None = None,
        db_port: int | None = None,
        db_name: str | None = None,
        db_user: str | None = None,
        db_password: str | None = None,
        openai_api_key: str | None = None,
        embedding_model: str = "text-embedding-3-large",
        embedding_dims: int = 3072,
    ) -> None:
        self._db_host = db_host or os.getenv("POSTGRES_HOST", "localhost")
        self._db_port = db_port or int(os.getenv("POSTGRES_PORT", "5432"))
        self._db_name = db_name or os.getenv("POSTGRES_DB", "prism_phase1")
        self._db_user = db_user or os.getenv("POSTGRES_USER", os.getenv("USER", "postgres"))
        self._db_password = db_password or os.getenv("POSTGRES_PASSWORD", "")
        self._embedding_model = embedding_model
        self._embedding_dims = embedding_dims

        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            self._openai = OpenAI(api_key=api_key)
        else:
            self._openai = None

    def _get_connection(self) -> psycopg.Connection[tuple[Any, ...]]:
        conninfo = f"host={self._db_host} port={self._db_port} dbname={self._db_name} user={self._db_user}"
        if self._db_password:
            conninfo += f" password={self._db_password}"
        return psycopg.connect(conninfo)

    def _embed_query(self, query: str) -> list[float]:
        if not self._openai:
            raise ValueError("OpenAI API key not set - cannot generate embeddings")
        response = self._openai.embeddings.create(
            model=self._embedding_model,
            input=query,
            dimensions=self._embedding_dims,
        )
        return response.data[0].embedding

    def search_keyword(
        self,
        query: str,
        *,
        limit: int = 10,
        repo_filter: str | None = None,
    ) -> list[KBDocument]:
        """Full-text search using PostgreSQL tsvector."""
        sql = """
            SELECT
                d.kb_id, d.item_type, d.item_number, d.section,
                d.source_ref, d.text, d.metadata,
                ts_rank(d.text_tsv, plainto_tsquery('simple', %s)) AS score
            FROM kb_document d
            WHERE d.text_tsv @@ plainto_tsquery('simple', %s)
        """
        params: list[Any] = [query, query]

        if repo_filter:
            sql += " AND d.repo_full_name = %s"
            params.append(repo_filter)

        sql += " ORDER BY score DESC LIMIT %s"
        params.append(limit)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [
            KBDocument(
                kb_id=row[0],
                item_type=row[1],
                item_number=row[2],
                section=row[3],
                source_ref=row[4],
                text=row[5][:500] if row[5] else "",
                metadata=row[6] or {},
                score=float(row[7]) if row[7] else None,
            )
            for row in rows
        ]

    def search_vector(
        self,
        query: str,
        *,
        limit: int = 10,
        repo_filter: str | None = None,
    ) -> list[KBDocument]:
        """Semantic search using pgvector embeddings."""
        query_embedding = self._embed_query(query)
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in query_embedding) + "]"

        sql = """
            SELECT
                d.kb_id, d.item_type, d.item_number, d.section,
                d.source_ref, d.text, d.metadata,
                (e.embedding <=> %s::vector) AS distance
            FROM kb_embedding e
            JOIN kb_document d ON d.kb_id = e.kb_id
            WHERE e.model = %s
        """
        params: list[Any] = [vector_literal, self._embedding_model]

        if repo_filter:
            sql += " AND d.repo_full_name = %s"
            params.append(repo_filter)

        sql += " ORDER BY distance ASC LIMIT %s"
        params.append(limit)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [
            KBDocument(
                kb_id=row[0],
                item_type=row[1],
                item_number=row[2],
                section=row[3],
                source_ref=row[4],
                text=row[5][:500] if row[5] else "",
                metadata=row[6] or {},
                score=1.0 - float(row[7]) if row[7] else None,
            )
            for row in rows
        ]

    def search_hybrid(
        self,
        query: str,
        *,
        limit: int = 10,
        keyword_weight: float = 0.3,
        vector_weight: float = 0.7,
        repo_filter: str | None = None,
    ) -> list[KBDocument]:
        """Hybrid search combining keyword and vector search with RRF."""
        keyword_results = self.search_keyword(query, limit=limit * 2, repo_filter=repo_filter)
        vector_results = self.search_vector(query, limit=limit * 2, repo_filter=repo_filter)

        scores: dict[str, float] = {}
        docs: dict[str, KBDocument] = {}
        k = 60

        for rank, doc in enumerate(keyword_results):
            rrf = 1.0 / (k + rank + 1)
            scores[doc.kb_id] = scores.get(doc.kb_id, 0) + keyword_weight * rrf
            docs[doc.kb_id] = doc

        for rank, doc in enumerate(vector_results):
            rrf = 1.0 / (k + rank + 1)
            scores[doc.kb_id] = scores.get(doc.kb_id, 0) + vector_weight * rrf
            docs[doc.kb_id] = doc

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]

        return [
            KBDocument(
                kb_id=docs[kb_id].kb_id,
                item_type=docs[kb_id].item_type,
                item_number=docs[kb_id].item_number,
                section=docs[kb_id].section,
                source_ref=docs[kb_id].source_ref,
                text=docs[kb_id].text,
                metadata=docs[kb_id].metadata,
                score=scores[kb_id],
            )
            for kb_id in sorted_ids
        ]

    def format_references(self, docs: list[KBDocument]) -> list[str]:
        """Format KB documents as reference strings for the response agent."""
        refs = []
        for doc in docs:
            ref = f"[{doc.item_type.upper()} #{doc.item_number}] {doc.section}: {doc.text[:200]}..."
            if doc.source_ref:
                ref += f"\nSource: {doc.source_ref}"
            refs.append(ref)
        return refs
