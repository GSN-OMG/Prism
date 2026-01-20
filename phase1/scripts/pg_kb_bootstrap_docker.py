#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bootstrap Postgres (Docker) and build KB tables from raw_http.")
    p.add_argument("--raw-http-dir", required=True, help="Path to raw_http directory.")
    p.add_argument("--compose-file", default="docker-compose.postgres.yml", help="Compose file path (default: docker-compose.postgres.yml).")
    p.add_argument("--views-dir", default="out_views", help="Where to write CSV views (default: out_views).")
    p.add_argument("--db-user", default="prism")
    p.add_argument("--db-name", default="prism_phase1")
    p.add_argument("--wait-seconds", type=int, default=60, help="Max seconds to wait for DB readiness.")
    return p.parse_args()


def run(cmd: list[str], *, cwd: str) -> None:
    proc = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")


def main() -> int:
    args = parse_args()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    compose_path = os.path.join(repo_root, args.compose_file)
    raw_http_dir = args.raw_http_dir
    views_dir = os.path.join(repo_root, args.views_dir)

    if not os.path.isdir(raw_http_dir):
        print(f"raw_http dir not found: {raw_http_dir}", file=sys.stderr)
        return 2
    if not os.path.isfile(compose_path):
        print(f"compose file not found: {compose_path}", file=sys.stderr)
        return 2

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

    # 2) Start DB container.
    run(["docker", "compose", "-f", compose_path, "up", "-d"], cwd=repo_root)

    # 3) Wait for readiness.
    deadline = time.time() + max(1, args.wait_seconds)
    while time.time() < deadline:
        proc = subprocess.run(
            ["docker", "compose", "-f", compose_path, "exec", "-T", "db", "pg_isready", "-U", args.db_user, "-d", args.db_name],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            break
        time.sleep(1.0)
    else:
        print("DB did not become ready in time.", file=sys.stderr)
        return 2

    # 4) Apply schema + load views + build kb docs.
    for sql_path in ("/sql/001_schema.sql", "/sql/002_load_views.psql", "/sql/003_build_kb_documents.sql"):
        run(
            [
                "docker",
                "compose",
                "-f",
                compose_path,
                "exec",
                "-T",
                "db",
                "psql",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                args.db_user,
                "-d",
                args.db_name,
                "-f",
                sql_path,
            ],
            cwd=repo_root,
        )

    print("KB bootstrap complete.")
    print("Try:")
    print(f"  docker compose -f {compose_path} exec db psql -U {args.db_user} -d {args.db_name} -c \"select count(*) from kb_document;\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
