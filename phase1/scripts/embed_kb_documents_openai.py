#!/usr/bin/env python3
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Embed kb_document rows using OpenAI embeddings and upsert into kb_embedding.")
    p.add_argument("--db-name", default="prism_phase1")
    p.add_argument("--db-user", default=os.environ.get("USER", "postgres"))
    p.add_argument("--port", type=int, default=5432)
    p.add_argument("--model", default="text-embedding-3-large")
    p.add_argument("--dimensions", type=int, default=3072, help="Embedding dimension (default matches text-embedding-3-large).")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--max-docs", type=int, default=0, help="If >0, stop after embedding this many documents.")
    p.add_argument("--sleep-seconds", type=float, default=0.0, help="Optional sleep between batches.")
    p.add_argument("--dry-run", action="store_true", help="Only show how many docs would be embedded.")
    return p.parse_args()


def run(cmd: list[str], *, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def find_psql() -> str:
    # Prefer PATH.
    p = shutil.which("psql")
    if p:
        return p
    # Prefer Homebrew postgresql@17.
    candidate = "/opt/homebrew/opt/postgresql@17/bin/psql"
    if os.path.isfile(candidate):
        return candidate
    raise RuntimeError("psql not found. Ensure Postgres is installed and psql is on PATH.")


def psql_query(psql: str, *, user: str, port: int, db: str, sql: str) -> str:
    proc = run([psql, "-v", "ON_ERROR_STOP=1", "-U", user, "-p", str(port), "-d", db, "-tA", "-c", sql], cwd=os.getcwd())
    if proc.returncode != 0:
        raise RuntimeError(f"psql failed.\nSQL:\n{sql}\nSTDERR:\n{proc.stderr}")
    return proc.stdout


def psql_exec_file(psql: str, *, user: str, port: int, db: str, path: str) -> None:
    proc = run([psql, "-v", "ON_ERROR_STOP=1", "-U", user, "-p", str(port), "-d", db, "-f", path], cwd=os.getcwd())
    if proc.returncode != 0:
        raise RuntimeError(f"psql failed.\nFILE: {path}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")


def fetch_pending_docs(psql: str, *, user: str, port: int, db: str, model: str, limit: int) -> list[dict]:
    # Return as JSON lines-ish via row_to_json for stability.
    sql = (
        "WITH pending AS ("
        "  SELECT d.kb_id, d.text, d.source_hash "
        "  FROM kb_document d "
        "  LEFT JOIN kb_embedding e ON e.kb_id = d.kb_id AND e.model = "
        + sql_quote(model)
        + " "
        "  WHERE e.kb_id IS NULL OR e.source_hash <> d.source_hash "
        "  ORDER BY d.kb_id "
        f"  LIMIT {int(limit)}"
        ") "
        "SELECT coalesce(string_agg(row_to_json(pending)::text, E'\\n'), '') FROM pending;"
    )
    out = psql_query(psql, user=user, port=port, db=db, sql=sql).strip()
    if not out:
        return []
    rows = []
    for line in out.splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def sql_quote(text: str) -> str:
    return "'" + (text or "").replace("'", "''") + "'"


def vector_literal(values: list[float]) -> str:
    # pgvector accepts: '[1,2,3]'::vector
    # Use compact formatting to reduce SQL size.
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def openai_embed_batch(*, api_key: str, model: str, inputs: list[str], dimensions: int) -> list[list[float]]:
    body = {"model": model, "input": inputs}
    # dimensions is supported for text-embedding-3-* models; keep optional but explicit.
    if dimensions and isinstance(dimensions, int) and dimensions > 0:
        body["dimensions"] = dimensions

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_EMBEDDINGS_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    attempt = 0
    while True:
        attempt += 1
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            items = payload.get("data") or []
            if not isinstance(items, list) or len(items) != len(inputs):
                raise RuntimeError(f"Unexpected embeddings response shape (items={type(items)} len={len(items) if isinstance(items, list) else 'n/a'}).")
            out: list[list[float]] = []
            for it in items:
                emb = (it or {}).get("embedding")
                if not isinstance(emb, list) or not emb:
                    raise RuntimeError("Missing embedding in response.")
                out.append([float(x) for x in emb])
            return out
        except urllib.error.HTTPError as e:
            status = getattr(e, "code", 0) or 0
            body_text = ""
            try:
                body_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if status in (429, 500, 502, 503, 504) and attempt <= 8:
                sleep_s = min(2 ** (attempt - 1), 60) + random.random()
                time.sleep(sleep_s)
                continue
            raise RuntimeError(f"OpenAI HTTP {status}: {body_text[:500]}") from e
        except Exception as e:
            if attempt <= 5:
                time.sleep(min(2 ** (attempt - 1), 30) + random.random())
                continue
            raise


def upsert_embeddings(
    psql: str,
    *,
    user: str,
    port: int,
    db: str,
    model: str,
    dims: int,
    rows: list[dict],
    embeddings: list[list[float]],
) -> None:
    if len(rows) != len(embeddings):
        raise RuntimeError("rows/embeddings length mismatch")

    # Write a temp SQL file to avoid giant command lines.
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".sql") as f:
        path = f.name
        f.write("BEGIN;\n")
        for row, emb in zip(rows, embeddings):
            kb_id = str(row.get("kb_id") or "")
            source_hash = str(row.get("source_hash") or "")
            if not kb_id:
                continue
            vec = vector_literal(emb)
            f.write(
                "INSERT INTO kb_embedding(kb_id, model, dims, embedding, source_hash)\n"
                f"VALUES ({sql_quote(kb_id)}, {sql_quote(model)}, {int(dims)}, {sql_quote(vec)}::vector, {sql_quote(source_hash)})\n"
                "ON CONFLICT (kb_id, model) DO UPDATE SET\n"
                "  dims = EXCLUDED.dims,\n"
                "  embedding = EXCLUDED.embedding,\n"
                "  source_hash = EXCLUDED.source_hash,\n"
                "  created_at = now();\n"
            )
        f.write("COMMIT;\n")

    try:
        psql_exec_file(psql, user=user, port=port, db=db, path=path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def main() -> int:
    args = parse_args()
    psql = find_psql()

    # Ensure the extension/table exists (schema should have been applied earlier).
    _ = psql_query(psql, user=args.db_user, port=args.port, db=args.db_name, sql="select 1;")

    if args.dry_run:
        pending_count = int(
            psql_query(
                psql,
                user=args.db_user,
                port=args.port,
                db=args.db_name,
                sql=(
                    "SELECT count(*) FROM kb_document d "
                    "LEFT JOIN kb_embedding e ON e.kb_id = d.kb_id AND e.model = "
                    + sql_quote(args.model)
                    + " "
                    "WHERE e.kb_id IS NULL OR e.source_hash <> d.source_hash;"
                ),
            ).strip()
            or "0"
        )
        print(f"Would embed {pending_count} document(s) for model={args.model}.")
        return 0

    api_key = os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        print("Missing OPENAI_API_KEY env var.", file=sys.stderr)
        return 2

    total_embedded = 0
    while True:
        rows = fetch_pending_docs(psql, user=args.db_user, port=args.port, db=args.db_name, model=args.model, limit=args.batch_size)
        if not rows:
            break

        texts = [str(r.get("text") or "") for r in rows]
        embeddings = openai_embed_batch(api_key=api_key, model=args.model, inputs=texts, dimensions=args.dimensions)

        # Basic dimension guard (schema is vector(3072) by default).
        if embeddings and (len(embeddings[0]) != int(args.dimensions)):
            raise RuntimeError(f"Embedding dims mismatch: expected {args.dimensions}, got {len(embeddings[0])}")

        upsert_embeddings(
            psql,
            user=args.db_user,
            port=args.port,
            db=args.db_name,
            model=args.model,
            dims=int(args.dimensions),
            rows=rows,
            embeddings=embeddings,
        )

        total_embedded += len(rows)
        print(f"Embedded {len(rows)} docs (total={total_embedded})")

        if args.max_docs and total_embedded >= args.max_docs:
            break
        if args.sleep_seconds and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    print(f"Done. Embedded {total_embedded} document(s) into kb_embedding for model={args.model}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
