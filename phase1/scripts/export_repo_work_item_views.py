#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.parse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export relational-friendly work-item views from raw_http JSON records.")
    p.add_argument("--raw-http-dir", required=True, help="Path to raw_http directory (contains tag/ subdirs with *.json).")
    p.add_argument("--out-dir", default="out_views", help="Output directory for CSV files (default: out_views).")
    p.add_argument("--no-headers", action="store_true", help="Do not write CSV header rows.")
    p.add_argument("--max-body-chars", type=int, default=280, help="Max chars for comment/review body excerpts.")
    p.add_argument("--max-item-body-chars", type=int, default=800, help="Max chars for Issue/PR body excerpts.")
    return p.parse_args()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def iter_json_files(raw_http_dir: str):
    for root, _dirs, files in os.walk(raw_http_dir):
        for name in files:
            if not name.endswith(".json"):
                continue
            yield os.path.join(root, name)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_time(value: str | None) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
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


def derive_number(record: dict) -> int | None:
    body = (record.get("request") or {}).get("body")
    if not isinstance(body, dict):
        return None
    variables = body.get("variables")
    if not isinstance(variables, dict):
        return None
    n = variables.get("number")
    return n if isinstance(n, int) else None


def actor_login(actor: dict) -> str | None:
    if not isinstance(actor, dict):
        return None
    login = actor.get("login")
    if isinstance(login, str) and login:
        return "@" + login.lstrip("@")
    return None


def build_work_item_url(repo_full_name: str, item_type: str, number: int) -> str:
    owner, name = repo_full_name.split("/", 1)
    path = "issues" if item_type == "issue" else "pull"
    return f"https://github.com/{owner}/{name}/{path}/{number}"


def safe_excerpt(text: str | None, *, max_chars: int) -> str:
    if not isinstance(text, str) or not text:
        return ""
    s = re.sub(r"\s+", " ", text).strip()
    if len(s) <= max_chars:
        return s
    # Preserve a stable excerpt for diffing/review.
    return s[: max(0, max_chars - 1)] + "…"


def sha256_12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def extract_work_item_from_core(*, repo: str, item: dict, max_item_body_chars: int) -> dict | None:
    typename = item.get("__typename")
    if typename not in ("Issue", "PullRequest"):
        return None

    number = item.get("number")
    if not isinstance(number, int):
        return None

    item_type = "pr" if typename == "PullRequest" else "issue"
    url = item.get("url") if isinstance(item.get("url"), str) else build_work_item_url(repo, item_type, number)

    created_at = parse_time(item.get("createdAt"))
    closed_at = parse_time(item.get("closedAt"))
    merged_at = parse_time(item.get("mergedAt")) if typename == "PullRequest" else None

    labels = []
    for n in ((item.get("labels") or {}).get("nodes") or []):
        if isinstance(n, dict) and isinstance(n.get("name"), str) and n.get("name"):
            labels.append(n["name"])
    labels = sorted(set(labels))

    milestone_title = None
    milestone = item.get("milestone")
    if isinstance(milestone, dict) and isinstance(milestone.get("title"), str):
        milestone_title = milestone.get("title")

    comments_total = None
    comments = item.get("comments")
    if isinstance(comments, dict) and isinstance(comments.get("totalCount"), int):
        comments_total = comments.get("totalCount")

    reviews_total = None
    if typename == "PullRequest":
        reviews = item.get("reviews")
        if isinstance(reviews, dict) and isinstance(reviews.get("totalCount"), int):
            reviews_total = reviews.get("totalCount")

    return {
        "repo_full_name": repo,
        "number": number,
        "type": item_type,
        "url": url,
        "title": item.get("title") if isinstance(item.get("title"), str) else "",
        "body_excerpt": safe_excerpt(item.get("body"), max_chars=max_item_body_chars),
        "state": item.get("state") if isinstance(item.get("state"), str) else "",
        "created_at": time_to_iso(created_at) if created_at else "",
        "closed_at": time_to_iso(closed_at) if closed_at else "",
        "author_login": actor_login(item.get("author") or {}) or "",
        "author_association": item.get("authorAssociation") if isinstance(item.get("authorAssociation"), str) else "",
        "labels_json": json.dumps(labels, ensure_ascii=False),
        "milestone_title": milestone_title or "",
        "is_merged": "1" if (typename == "PullRequest" and merged_at is not None) else "0",
        "merged_at": time_to_iso(merged_at) if merged_at else "",
        "merged_by": actor_login(item.get("mergedBy") or {}) if typename == "PullRequest" else "",
        "comment_count": str(comments_total) if isinstance(comments_total, int) else "",
        "review_count": str(reviews_total) if isinstance(reviews_total, int) else "",
        "changed_files": str(item.get("changedFiles")) if isinstance(item.get("changedFiles"), int) else "",
        "additions": str(item.get("additions")) if isinstance(item.get("additions"), int) else "",
        "deletions": str(item.get("deletions")) if isinstance(item.get("deletions"), int) else "",
    }


def extract_events_from_timeline(*, repo: str, record: dict, timeline_nodes: list, item_type: str, number: int) -> list[dict]:
    ref = build_work_item_url(repo, item_type, number)
    out: list[dict] = []
    for ev in timeline_nodes:
        if not isinstance(ev, dict):
            continue
        ev_type = ev.get("__typename")
        if not isinstance(ev_type, str) or not ev_type:
            continue
        occurred_at = parse_time(ev.get("createdAt"))
        if occurred_at is None:
            continue
        actor = actor_login(ev.get("actor") or {}) or ""

        subject_type = ""
        subject = ""
        if ev_type in ("LabeledEvent", "UnlabeledEvent"):
            label = ev.get("label") or {}
            if isinstance(label, dict) and isinstance(label.get("name"), str):
                subject_type = "label"
                subject = label["name"]
        elif ev_type in ("MilestonedEvent", "DemilestonedEvent"):
            if isinstance(ev.get("milestoneTitle"), str):
                subject_type = "milestone"
                subject = ev["milestoneTitle"]
        elif ev_type in ("AssignedEvent", "UnassignedEvent"):
            assignee = ev.get("assignee") or {}
            if isinstance(assignee, dict) and isinstance(assignee.get("login"), str):
                subject_type = "assignee"
                subject = assignee["login"]
        elif ev_type in ("CrossReferencedEvent",):
            source = ev.get("source") or {}
            if isinstance(source, dict) and isinstance(source.get("url"), str):
                subject_type = "source"
                subject = source["url"]
        elif ev_type in ("ReferencedEvent",):
            commit = ev.get("commit") or {}
            if isinstance(commit, dict) and isinstance(commit.get("url"), str):
                subject_type = "commit"
                subject = commit["url"]

        out.append(
            {
                "repo_full_name": repo,
                "number": number,
                "type": item_type,
                "event_id": ev.get("id") if isinstance(ev.get("id"), str) else "",
                "event_type": ev_type,
                "occurred_at": time_to_iso(occurred_at),
                "actor_login": actor,
                "subject_type": subject_type,
                "subject": subject,
                "reference": ref,
            }
        )
    return out


def extract_comment_rows(*, repo: str, nodes: list, item_type: str, number: int, max_body_chars: int) -> list[dict]:
    out: list[dict] = []
    for c in nodes:
        if not isinstance(c, dict):
            continue
        created_at = parse_time(c.get("createdAt"))
        if created_at is None:
            continue
        comment_id = c.get("id") if isinstance(c.get("id"), str) and c.get("id") else ""
        if not comment_id:
            # Keep a stable surrogate key.
            comment_id = "sha256:" + sha256_12(json.dumps(c, sort_keys=True, ensure_ascii=False))
        out.append(
            {
                "repo_full_name": repo,
                "number": number,
                "type": item_type,
                "comment_id": comment_id,
                "url": c.get("url") if isinstance(c.get("url"), str) else "",
                "created_at": time_to_iso(created_at),
                "author_login": actor_login(c.get("author") or {}) or "",
                "author_association": c.get("authorAssociation") if isinstance(c.get("authorAssociation"), str) else "",
                "body_excerpt": safe_excerpt(c.get("body"), max_chars=max_body_chars),
            }
        )
    return out


def extract_review_rows(*, repo: str, nodes: list, pr_number: int, max_body_chars: int) -> list[dict]:
    out: list[dict] = []
    ref = build_work_item_url(repo, "pr", pr_number)
    for r in nodes:
        if not isinstance(r, dict):
            continue
        submitted_at = parse_time(r.get("submittedAt"))
        if submitted_at is None:
            continue
        rid = r.get("id") if isinstance(r.get("id"), str) and r.get("id") else ""
        if not rid:
            rid = "sha256:" + sha256_12(json.dumps(r, sort_keys=True, ensure_ascii=False))
        out.append(
            {
                "repo_full_name": repo,
                "pr_number": pr_number,
                "review_id": rid,
                "review_state": r.get("state") if isinstance(r.get("state"), str) else "",
                "submitted_at": time_to_iso(submitted_at),
                "author_login": actor_login(r.get("author") or {}) or "",
                "body_excerpt": safe_excerpt(r.get("body"), max_chars=max_body_chars),
                "reference": ref,
            }
        )
    return out


def extract_rows_from_record(
    record: dict, *, max_body_chars: int, max_item_body_chars: int
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    Returns:
      work_items, events, comments, pr_reviews
    """
    work_items: list[dict] = []
    events: list[dict] = []
    comments: list[dict] = []
    pr_reviews: list[dict] = []

    repo = derive_repo_full_name(record)
    if not repo:
        return work_items, events, comments, pr_reviews

    tag = (record.get("meta") or {}).get("tag") or ""
    resp = (record.get("response") or {}).get("json")
    if not isinstance(resp, dict):
        return work_items, events, comments, pr_reviews

    data = resp.get("data") or {}
    if not isinstance(data, dict):
        return work_items, events, comments, pr_reviews

    if isinstance(tag, str) and tag.startswith("graphql_core_item"):
        item = (data.get("repository") or {}).get("issueOrPullRequest") or {}
        if isinstance(item, dict):
            row = extract_work_item_from_core(repo=repo, item=item, max_item_body_chars=max_item_body_chars)
            if row:
                work_items.append(row)
        return work_items, events, comments, pr_reviews

    if isinstance(tag, str) and tag.startswith("graphql_timeline_item"):
        iorp = (data.get("repository") or {}).get("issueOrPullRequest") or {}
        if not isinstance(iorp, dict):
            return work_items, events, comments, pr_reviews
        typename = iorp.get("__typename")
        if typename not in ("Issue", "PullRequest"):
            return work_items, events, comments, pr_reviews
        number = derive_number(record)
        if number is None:
            return work_items, events, comments, pr_reviews
        item_type = "pr" if typename == "PullRequest" else "issue"
        timeline_nodes = ((iorp.get("timelineItems") or {}).get("nodes") or [])
        if isinstance(timeline_nodes, list):
            events.extend(extract_events_from_timeline(repo=repo, record=record, timeline_nodes=timeline_nodes, item_type=item_type, number=number))
        return work_items, events, comments, pr_reviews

    if isinstance(tag, str) and tag.startswith("graphql_comments_item"):
        iorp = (data.get("repository") or {}).get("issueOrPullRequest") or {}
        if not isinstance(iorp, dict):
            return work_items, events, comments, pr_reviews
        typename = iorp.get("__typename")
        if typename not in ("Issue", "PullRequest"):
            return work_items, events, comments, pr_reviews
        number = derive_number(record)
        if number is None:
            return work_items, events, comments, pr_reviews
        item_type = "pr" if typename == "PullRequest" else "issue"
        comment_nodes = ((iorp.get("comments") or {}).get("nodes") or [])
        if isinstance(comment_nodes, list):
            comments.extend(extract_comment_rows(repo=repo, nodes=comment_nodes, item_type=item_type, number=number, max_body_chars=max_body_chars))
        return work_items, events, comments, pr_reviews

    if isinstance(tag, str) and tag.startswith("graphql_reviews_pr"):
        pr = (data.get("repository") or {}).get("pullRequest") or {}
        if not isinstance(pr, dict):
            return work_items, events, comments, pr_reviews
        number = derive_number(record)
        if number is None:
            return work_items, events, comments, pr_reviews
        review_nodes = ((pr.get("reviews") or {}).get("nodes") or [])
        if isinstance(review_nodes, list):
            pr_reviews.extend(extract_review_rows(repo=repo, nodes=review_nodes, pr_number=number, max_body_chars=max_body_chars))
        return work_items, events, comments, pr_reviews

    return work_items, events, comments, pr_reviews


def write_csv(path: str, rows: list[dict], *, fieldnames: list[str], write_header: bool) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    args = parse_args()
    raw_http_dir = args.raw_http_dir
    out_dir = args.out_dir
    max_body_chars = args.max_body_chars
    max_item_body_chars = args.max_item_body_chars

    if not os.path.isdir(raw_http_dir):
        print(f"raw_http dir not found: {raw_http_dir}", file=sys.stderr)
        return 2

    ensure_dir(out_dir)

    work_items: dict[tuple[str, int, str], dict] = {}
    events: list[dict] = []
    comments: list[dict] = []
    reviews: list[dict] = []

    for path in iter_json_files(raw_http_dir):
        try:
            record = load_json(path)
        except Exception:
            continue
        wi_rows, ev_rows, c_rows, r_rows = extract_rows_from_record(
            record, max_body_chars=max_body_chars, max_item_body_chars=max_item_body_chars
        )
        for wi in wi_rows:
            key = (wi["repo_full_name"], int(wi["number"]), wi["type"])
            work_items[key] = wi
        events.extend(ev_rows)
        comments.extend(c_rows)
        reviews.extend(r_rows)

    work_item_rows = sorted(work_items.values(), key=lambda r: (r["repo_full_name"], int(r["number"]), r["type"]))
    event_rows = sorted(events, key=lambda r: (r["repo_full_name"], int(r["number"]), r["occurred_at"], r["event_type"], r.get("event_id", "")))
    comment_rows = sorted(comments, key=lambda r: (r["repo_full_name"], int(r["number"]), r["created_at"], r.get("comment_id", "")))
    review_rows = sorted(reviews, key=lambda r: (r["repo_full_name"], int(r["pr_number"]), r["submitted_at"], r.get("review_id", "")))

    p_work_items = os.path.join(out_dir, "repo_work_item.csv")
    p_events = os.path.join(out_dir, "repo_work_item_event.csv")
    p_comments = os.path.join(out_dir, "repo_comment.csv")
    p_reviews = os.path.join(out_dir, "repo_pr_review.csv")

    write_csv(
        p_work_items,
        work_item_rows,
        fieldnames=[
            "repo_full_name",
            "number",
            "type",
            "url",
            "title",
            "body_excerpt",
            "state",
            "created_at",
            "closed_at",
            "author_login",
            "author_association",
            "labels_json",
            "milestone_title",
            "is_merged",
            "merged_at",
            "merged_by",
            "comment_count",
            "review_count",
            "changed_files",
            "additions",
            "deletions",
        ],
        write_header=not args.no_headers,
    )
    write_csv(
        p_events,
        event_rows,
        fieldnames=[
            "repo_full_name",
            "number",
            "type",
            "event_id",
            "event_type",
            "occurred_at",
            "actor_login",
            "subject_type",
            "subject",
            "reference",
        ],
        write_header=not args.no_headers,
    )
    write_csv(
        p_comments,
        comment_rows,
        fieldnames=[
            "repo_full_name",
            "number",
            "type",
            "comment_id",
            "url",
            "created_at",
            "author_login",
            "author_association",
            "body_excerpt",
        ],
        write_header=not args.no_headers,
    )
    write_csv(
        p_reviews,
        review_rows,
        fieldnames=[
            "repo_full_name",
            "pr_number",
            "review_id",
            "review_state",
            "submitted_at",
            "author_login",
            "body_excerpt",
            "reference",
        ],
        write_header=not args.no_headers,
    )

    print(f"Wrote {len(work_item_rows)} work items: {p_work_items}")
    print(f"Wrote {len(event_rows)} timeline events: {p_events}")
    print(f"Wrote {len(comment_rows)} comments: {p_comments}")
    print(f"Wrote {len(review_rows)} PR reviews: {p_reviews}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
