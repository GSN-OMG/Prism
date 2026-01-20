#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import time


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bootstrap local Postgres (Homebrew) and build KB tables from raw_http.")
    p.add_argument("--raw-http-dir", required=True, help="Path to raw_http directory.")
    p.add_argument("--views-dir", default="out_views", help="Where to write CSV views (default: out_views).")
    p.add_argument("--db-name", default="prism_phase1")
    p.add_argument("--db-user", default=os.environ.get("USER", "postgres"))
    p.add_argument("--port", type=int, default=5432)
    p.add_argument("--wait-seconds", type=int, default=60, help="Max seconds to wait for DB readiness.")
    p.add_argument("--postgres-formula", default="postgresql@17", help="Homebrew formula to start (default: postgresql@17).")
    return p.parse_args()


def run(cmd: list[str], *, cwd: str, env: dict | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, env=env, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")


def find_pg_bin(tool: str, *, formula: str) -> str:
    # Prefer PATH.
    p = shutil.which(tool)
    if p:
        return p
    # Try Homebrew opt path.
    candidate = os.path.join("/opt/homebrew/opt", formula, "bin", tool)
    if os.path.isfile(candidate):
        return candidate
    # Last resort: ask brew for prefix.
    proc = subprocess.run(["brew", "--prefix", formula], check=False, capture_output=True, text=True)
    prefix = (proc.stdout or "").strip()
    if proc.returncode == 0 and prefix:
        candidate2 = os.path.join(prefix, "bin", tool)
        if os.path.isfile(candidate2):
            return candidate2
    raise RuntimeError(f"Could not find '{tool}'. Install {formula} and ensure binaries are available.")


def wait_ready(*, pg_isready: str, user: str, port: int, wait_seconds: int) -> None:
    deadline = time.time() + max(1, wait_seconds)
    while time.time() < deadline:
        proc = subprocess.run([pg_isready, "-U", user, "-p", str(port)], check=False, capture_output=True, text=True)
        if proc.returncode == 0:
            return
        time.sleep(1.0)
    raise RuntimeError("Postgres did not become ready in time.")


def ensure_database_exists(*, createdb: str, psql: str, db_name: str, user: str, port: int) -> None:
    check_sql = f"select 1 from pg_database where datname = '{db_name}';"
    proc = subprocess.run(
        [psql, "-U", user, "-p", str(port), "-d", "postgres", "-tAc", check_sql],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to query pg_database.\nSTDERR:\n{proc.stderr}")
    exists = (proc.stdout or "").strip() == "1"
    if exists:
        return
    run([createdb, "-U", user, "-p", str(port), db_name], cwd=os.getcwd())


def main() -> int:
    args = parse_args()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_http_dir = args.raw_http_dir
    views_dir = os.path.join(repo_root, args.views_dir)

    if not os.path.isdir(raw_http_dir):
        print(f"raw_http dir not found: {raw_http_dir}", file=sys.stderr)
        return 2

    # Find postgres tools.
    psql = find_pg_bin("psql", formula=args.postgres_formula)
    createdb = find_pg_bin("createdb", formula=args.postgres_formula)
    pg_isready = find_pg_bin("pg_isready", formula=args.postgres_formula)

    # 1) Export views from raw_http (bounded excerpts only).
    run(
        [
            sys.executable,
            os.path.join(repo_root, "scripts", "export_repo_work_item_views.py"),
            "--raw-http-dir",
            raw_http_dir,
            "--out-dir",
            views_dir,
        ],
        cwd=repo_root,
    )

    # 2) Start Postgres via brew services (local install requirement).
    run(["brew", "services", "start", args.postgres_formula], cwd=repo_root)

    # 3) Wait and ensure db exists.
    wait_ready(pg_isready=pg_isready, user=args.db_user, port=args.port, wait_seconds=args.wait_seconds)
    ensure_database_exists(createdb=createdb, psql=psql, db_name=args.db_name, user=args.db_user, port=args.port)

    # 4) Apply schema.
    run([psql, "-v", "ON_ERROR_STOP=1", "-U", args.db_user, "-p", str(args.port), "-d", args.db_name, "-f", os.path.join(repo_root, "sql", "001_schema.sql")], cwd=repo_root)

    # 5) Load views (use psql meta-command \copy with absolute paths).
    p_work_item = os.path.join(views_dir, "repo_work_item.csv")
    p_event = os.path.join(views_dir, "repo_work_item_event.csv")
    p_comment = os.path.join(views_dir, "repo_comment.csv")
    p_review = os.path.join(views_dir, "repo_pr_review.csv")

    run(
        [
            psql,
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            args.db_user,
            "-p",
            str(args.port),
            "-d",
            args.db_name,
            "-c",
            "TRUNCATE TABLE repo_work_item, repo_work_item_event, repo_comment, repo_pr_review;",
        ],
        cwd=repo_root,
    )
    run(
        [
            psql,
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            args.db_user,
            "-p",
            str(args.port),
            "-d",
            args.db_name,
            "-c",
            "\\copy repo_work_item(repo_full_name,number,type,url,title,body_excerpt,state,created_at,closed_at,author_login,author_association,labels_json,milestone_title,is_merged,merged_at,merged_by,comment_count,review_count,changed_files,additions,deletions) FROM '"
            + p_work_item.replace("'", "''")
            + "' CSV HEADER;",
        ],
        cwd=repo_root,
    )
    run(
        [
            psql,
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            args.db_user,
            "-p",
            str(args.port),
            "-d",
            args.db_name,
            "-c",
            "\\copy repo_work_item_event(repo_full_name,number,type,event_id,event_type,occurred_at,actor_login,subject_type,subject,reference) FROM '"
            + p_event.replace("'", "''")
            + "' CSV HEADER;",
        ],
        cwd=repo_root,
    )
    run(
        [
            psql,
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            args.db_user,
            "-p",
            str(args.port),
            "-d",
            args.db_name,
            "-c",
            "\\copy repo_comment(repo_full_name,number,type,comment_id,url,created_at,author_login,author_association,body_excerpt) FROM '"
            + p_comment.replace("'", "''")
            + "' CSV HEADER;",
        ],
        cwd=repo_root,
    )
    run(
        [
            psql,
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            args.db_user,
            "-p",
            str(args.port),
            "-d",
            args.db_name,
            "-c",
            "\\copy repo_pr_review(repo_full_name,pr_number,review_id,review_state,submitted_at,author_login,body_excerpt,reference) FROM '"
            + p_review.replace("'", "''")
            + "' CSV HEADER;",
        ],
        cwd=repo_root,
    )

    # 6) Build kb_document.
    run([psql, "-v", "ON_ERROR_STOP=1", "-U", args.db_user, "-p", str(args.port), "-d", args.db_name, "-f", os.path.join(repo_root, "sql", "003_build_kb_documents.sql")], cwd=repo_root)

    print("Local Postgres KB bootstrap complete.")
    print("Try:")
    print(f"  {psql} -U {args.db_user} -p {args.port} -d {args.db_name} -c \"select count(*) from kb_document;\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
