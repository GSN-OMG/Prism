#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export repo_user / repo_user_activity CSVs from raw_http JSON records.")
    p.add_argument("--raw-http-dir", required=True, help="Path to raw_http directory (contains tag/ subdirs with *.json).")
    p.add_argument("--out-dir", default="out", help="Output directory for CSV files (default: out).")
    p.add_argument("--no-headers", action="store_true", help="Do not write CSV header rows.")
    return p.parse_args()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def parse_time(value: str | None) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # GitHub commonly returns Z.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def time_to_iso(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def iter_json_files(raw_http_dir: str):
    for root, _dirs, files in os.walk(raw_http_dir):
        for name in files:
            if not name.endswith(".json"):
                continue
            yield os.path.join(root, name)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def derive_repo_full_name(record: dict) -> str | None:
    # Prefer GraphQL variables.
    body = (record.get("request") or {}).get("body")
    if isinstance(body, dict):
        variables = body.get("variables")
        if isinstance(variables, dict):
            owner = variables.get("owner")
            name = variables.get("name")
            if isinstance(owner, str) and isinstance(name, str) and owner and name:
                return f"{owner}/{name}"

    # REST search includes repo:owner/name in q=
    url = (record.get("request") or {}).get("url")
    if not isinstance(url, str) or not url:
        return None
    parsed = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(parsed.query or "").get("q", [])
    if not q:
        return None
    q0 = q[0]
    m = re.search(r"\brepo:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b", q0)
    if not m:
        return None
    return m.group(1)


def build_work_item_url(repo_full_name: str, typename: str, number: int) -> str:
    owner, name = repo_full_name.split("/", 1)
    path = "issues" if typename == "Issue" else "pull"
    return f"https://github.com/{owner}/{name}/{path}/{number}"


def derive_number(record: dict) -> int | None:
    body = (record.get("request") or {}).get("body")
    if not isinstance(body, dict):
        return None
    variables = body.get("variables")
    if not isinstance(variables, dict):
        return None
    n = variables.get("number")
    return n if isinstance(n, int) else None


def actor_key(actor: dict) -> str | None:
    """
    Prefer a human-friendly identifier over opaque node ids.
    - login (e.g. 'seratch', 'github-actions') is what most people expect to see.
    - fallback to numeric id/databaseId when login is missing.
    - last fallback to node id.
    """
    if not isinstance(actor, dict):
        return None
    login = actor.get("login")
    if isinstance(login, str) and login:
        # GitHub-style user_id
        return "@" + login.lstrip("@")
    # If we don't have a login, we can't produce a stable GitHub user_id like '@mattlgroff'.
    return None


def extract_rows_from_record(record: dict) -> tuple[list[tuple], list[tuple]]:
    """
    Returns:
      activities: list of (repo_full_name, user_id, action, reference, occurred_at_iso)
      role_observations: list of (repo_full_name, user_id, role, observed_at_dt)
    """
    activities: list[tuple] = []
    role_observations: list[tuple] = []

    repo = derive_repo_full_name(record)
    if not repo:
        return activities, role_observations

    tag = (record.get("meta") or {}).get("tag") or ""
    resp = (record.get("response") or {}).get("json")
    if not isinstance(resp, dict):
        return activities, role_observations

    # REST discovery (search/issues)
    if isinstance(tag, str) and tag.startswith("discovery_"):
        items = resp.get("items") or []
        if not isinstance(items, list):
            return activities, role_observations
        for it in items:
            if not isinstance(it, dict):
                continue
            user = it.get("user") or {}
            if not isinstance(user, dict):
                continue
            user_id = actor_key(user)
            if not isinstance(user_id, str) or not user_id:
                continue
            role = it.get("author_association") or "NONE"
            if not isinstance(role, str) or not role:
                role = "NONE"
            occurred_at = parse_time(it.get("created_at"))
            if occurred_at is None:
                continue
            reference = it.get("html_url")
            if not isinstance(reference, str) or not reference:
                continue
            action = "pr_opened" if isinstance(it.get("pull_request"), dict) else "issue_opened"

            activities.append((repo, user_id, action, reference, time_to_iso(occurred_at)))
            role_observations.append((repo, user_id, role, occurred_at))

        return activities, role_observations

    # GraphQL payloads
    data = resp.get("data") or {}
    if not isinstance(data, dict):
        return activities, role_observations

    # GraphQL core item
    if isinstance(tag, str) and tag.startswith("graphql_core_item"):
        item = (
            data.get("repository", {})
            .get("issueOrPullRequest", {})
        )
        if not isinstance(item, dict):
            return activities, role_observations
        typename = item.get("__typename")
        if not isinstance(typename, str) or typename not in ("Issue", "PullRequest"):
            return activities, role_observations
        url = item.get("url")
        if not isinstance(url, str) or not url:
            return activities, role_observations

        created_at = parse_time(item.get("createdAt"))
        author = item.get("author") or {}
        author_id = actor_key(author) if isinstance(author, dict) else None
        role = item.get("authorAssociation") or "NONE"
        if created_at is not None and isinstance(author_id, str) and author_id:
            activities.append((repo, author_id, "pr_opened" if typename == "PullRequest" else "issue_opened", url, time_to_iso(created_at)))
            if isinstance(role, str) and role:
                role_observations.append((repo, author_id, role, created_at))

        if typename == "PullRequest":
            merged_at = parse_time(item.get("mergedAt"))
            merged_by = item.get("mergedBy") or {}
            merged_by_id = actor_key(merged_by) if isinstance(merged_by, dict) else None
            if merged_at is not None and isinstance(merged_by_id, str) and merged_by_id:
                activities.append((repo, merged_by_id, "pr_merged", url, time_to_iso(merged_at)))

        return activities, role_observations

    # GraphQL comments page (Issue or PullRequest)
    if isinstance(tag, str) and tag.startswith("graphql_comments_item"):
        iorp = (
            data.get("repository", {})
            .get("issueOrPullRequest", {})
        )
        if not isinstance(iorp, dict):
            return activities, role_observations
        typename = iorp.get("__typename")
        if not isinstance(typename, str) or typename not in ("Issue", "PullRequest"):
            return activities, role_observations
        number = derive_number(record)
        if number is None:
            return activities, role_observations
        reference = build_work_item_url(repo, typename, number)

        comments = (iorp.get("comments") or {}).get("nodes") or []
        if not isinstance(comments, list):
            return activities, role_observations
        for c in comments:
            if not isinstance(c, dict):
                continue
            occurred_at = parse_time(c.get("createdAt"))
            if occurred_at is None:
                continue
            author = c.get("author") or {}
            if not isinstance(author, dict):
                continue
            author_id = actor_key(author)
            if not isinstance(author_id, str) or not author_id:
                continue
            role = c.get("authorAssociation") or "NONE"
            if not isinstance(role, str) or not role:
                role = "NONE"
            activities.append((repo, author_id, "commented", reference, time_to_iso(occurred_at)))
            role_observations.append((repo, author_id, role, occurred_at))

        return activities, role_observations

    # GraphQL reviews page (PullRequest only)
    if isinstance(tag, str) and tag.startswith("graphql_reviews_pr"):
        pr = (data.get("repository", {}) or {}).get("pullRequest", {}) or {}
        if not isinstance(pr, dict):
            return activities, role_observations
        number = derive_number(record)
        if number is None:
            return activities, role_observations
        reference = build_work_item_url(repo, "PullRequest", number)

        reviews = (pr.get("reviews") or {}).get("nodes") or []
        if not isinstance(reviews, list):
            return activities, role_observations
        for r in reviews:
            if not isinstance(r, dict):
                continue
            occurred_at = parse_time(r.get("submittedAt"))
            if occurred_at is None:
                continue
            author = r.get("author") or {}
            if not isinstance(author, dict):
                continue
            author_id = actor_key(author)
            if not isinstance(author_id, str) or not author_id:
                continue
            activities.append((repo, author_id, "reviewed", reference, time_to_iso(occurred_at)))

        return activities, role_observations

    # GraphQL timeline page
    if isinstance(tag, str) and tag.startswith("graphql_timeline_item"):
        iorp = (
            data.get("repository", {})
            .get("issueOrPullRequest", {})
        )
        if not isinstance(iorp, dict):
            return activities, role_observations
        typename = iorp.get("__typename")
        if not isinstance(typename, str) or typename not in ("Issue", "PullRequest"):
            return activities, role_observations
        number = derive_number(record)
        if number is None:
            return activities, role_observations
        reference = build_work_item_url(repo, typename, number)

        timeline = (iorp.get("timelineItems") or {}).get("nodes") or []
        if not isinstance(timeline, list):
            return activities, role_observations

        typename_to_action = {
            "ClosedEvent": "closed",
            "ReopenedEvent": "reopened",
            "LabeledEvent": "labeled",
            "UnlabeledEvent": "unlabeled",
            "AssignedEvent": "assigned",
            "UnassignedEvent": "unassigned",
        }

        for ev in timeline:
            if not isinstance(ev, dict):
                continue
            action = typename_to_action.get(ev.get("__typename"))
            if not action:
                continue
            occurred_at = parse_time(ev.get("createdAt"))
            if occurred_at is None:
                continue
            actor = ev.get("actor") or {}
            if not isinstance(actor, dict):
                continue
            actor_id = actor_key(actor)
            if not isinstance(actor_id, str) or not actor_id:
                continue
            activities.append((repo, actor_id, action, reference, time_to_iso(occurred_at)))

        return activities, role_observations

    return activities, role_observations


def pick_latest_roles(role_observations: list[tuple]) -> dict[tuple[str, str], str]:
    latest: dict[tuple[str, str], tuple[dt.datetime, str]] = {}
    for repo, user_id, role, observed_at in role_observations:
        key = (repo, user_id)
        prev = latest.get(key)
        if prev is None or observed_at > prev[0]:
            latest[key] = (observed_at, role)
    return {k: v[1] for k, v in latest.items()}


def main() -> int:
    args = parse_args()
    raw_http_dir = args.raw_http_dir
    out_dir = args.out_dir

    if not os.path.isdir(raw_http_dir):
        print(f"raw_http dir not found: {raw_http_dir}", file=sys.stderr)
        return 2

    ensure_dir(out_dir)

    activities_set: set[tuple] = set()
    role_obs: list[tuple] = []

    for path in iter_json_files(raw_http_dir):
        try:
            record = load_json(path)
        except Exception:
            continue
        acts, roles = extract_rows_from_record(record)
        for a in acts:
            activities_set.add(a)
        role_obs.extend(roles)

    activities = sorted(activities_set, key=lambda r: (r[0], r[1], r[4], r[2], r[3]))
    latest_roles = pick_latest_roles(role_obs)

    all_users: set[tuple[str, str]] = set((repo, user_id) for (repo, user_id, _action, _ref, _t) in activities)
    repo_users = sorted(
        ((repo, user_id, latest_roles.get((repo, user_id), "NONE")) for (repo, user_id) in all_users),
        key=lambda r: (r[0], r[1]),
    )

    repo_user_csv = os.path.join(out_dir, "repo_user.csv")
    repo_user_activity_csv = os.path.join(out_dir, "repo_user_activity.csv")

    with open(repo_user_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not args.no_headers:
            w.writerow(["repo_full_name", "user_id", "role"])
        w.writerows(repo_users)

    with open(repo_user_activity_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not args.no_headers:
            w.writerow(["repo_full_name", "user_id", "action", "reference", "occurred_at"])
        w.writerows(activities)

    print(f"Wrote {len(repo_users)} repo_user rows: {repo_user_csv}")
    print(f"Wrote {len(activities)} repo_user_activity rows: {repo_user_activity_csv}")
    print("")
    print("PostgreSQL import (psql) example:")
    print(f"  \\copy repo_user(repo_full_name,user_id,role) FROM '{repo_user_csv}' CSV HEADER;")
    print(
        f"  \\copy repo_user_activity(repo_full_name,user_id,action,reference,occurred_at) FROM '{repo_user_activity_csv}' CSV HEADER;"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
