#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import sys
import time
import urllib.parse


GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"


def utc_now_compact() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "").replace("-", "") + "Z"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_write_json(path: str, payload: dict) -> None:
    ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def safe_write_text(path: str, text: str) -> None:
    ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def redact_headers(headers: dict) -> dict:
    redacted = {}
    for k, v in headers.items():
        if k.lower() in ("authorization",):
            continue
        redacted[k] = v
    return redacted


def http_request_json(
    *,
    method: str,
    url: str,
    headers: dict,
    body_obj: dict | None,
    timeout_s: int,
    max_retries: int,
    out_dir: str,
    tag: str,
) -> dict:
    body_bytes = None
    if body_obj is not None:
        body_bytes = json.dumps(body_obj).encode("utf-8")

    req_headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    req_headers.update(headers or {})
    if body_bytes is not None and "Content-Type" not in req_headers and "content-type" not in req_headers:
        req_headers["Content-Type"] = "application/json"

    if shutil.which("curl") is None:
        raise RuntimeError("curl not found on PATH; required due to Python SSL cert issues in this environment.")

    request_fingerprint = sha256_hex(
        json.dumps(
            {
                "method": method,
                "url": url,
                "headers": redact_headers(req_headers),
                "body": body_obj,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )[:16]

    attempt = 0
    last_error = None
    while attempt <= max_retries:
        attempt += 1
        started = dt.datetime.utcnow().isoformat() + "Z"
        try:
            ensure_dir(out_dir)
            header_tmp = tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=out_dir, prefix="curl_headers_", suffix=".txt")
            body_tmp = tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=out_dir, prefix="curl_body_", suffix=".txt")
            header_path = header_tmp.name
            body_path = body_tmp.name
            header_tmp.close()
            body_tmp.close()

            cmd = ["curl", "-sS", "-X", method, url, "-D", header_path, "-o", body_path, "--max-time", str(timeout_s)]
            auth_header_file = None
            try:
                # Avoid putting Authorization value into argv (visible to process lists):
                # curl supports -H @file to read header lines from a file.
                for k, v in req_headers.items():
                    if k.lower() == "authorization":
                        auth_header_file = tempfile.NamedTemporaryFile(
                            mode="w+", delete=False, dir=out_dir, prefix="curl_auth_", suffix=".txt"
                        )
                        auth_header_file.write(f"{k}: {v}\n")
                        auth_header_file.flush()
                        auth_header_file.close()
                        cmd.extend(["-H", f"@{auth_header_file.name}"])
                    else:
                        cmd.extend(["-H", f"{k}: {v}"])
            finally:
                # Deletion happens after curl runs; this is just to ensure file handle is closed.
                pass
            if body_bytes is not None:
                cmd.extend(["--data-binary", json.dumps(body_obj)])
            cmd.extend(["-w", "%{http_code}"])

            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if auth_header_file is not None:
                try:
                    os.unlink(auth_header_file.name)
                except OSError:
                    pass
            if proc.returncode != 0:
                last_error = RuntimeError(f"curl failed (code={proc.returncode}): {proc.stderr.strip()}")
                time.sleep(min(2**attempt, 60) + random.random())
                continue

            status_text = (proc.stdout or "").strip()
            status = int(status_text) if status_text.isdigit() else 0

            resp_headers = parse_curl_headers(header_path)
            body_text = read_text_file(body_path)
            try:
                os.unlink(header_path)
            except OSError:
                pass
            try:
                os.unlink(body_path)
            except OSError:
                pass
            try:
                data = json.loads(body_text)
            except json.JSONDecodeError:
                data = {"_non_json_body": body_text}

            record = {
                "started_at": started,
                "finished_at": dt.datetime.utcnow().isoformat() + "Z",
                "request": {
                    "method": method,
                    "url": url,
                    "headers": redact_headers(req_headers),
                    "body": body_obj,
                },
                "response": {
                    "status": status,
                    "headers": resp_headers,
                    "json": data,
                },
                "meta": {
                    "tag": tag,
                    "request_fingerprint": request_fingerprint,
                    "attempt": attempt,
                },
            }
            out_path = os.path.join(out_dir, "raw_http", tag, f"{request_fingerprint}_a{attempt}.json")
            safe_write_json(out_path, record)

            # Retry on rate-limit / transient.
            if status in (429, 500, 502, 503, 504):
                sleep_s = compute_retry_sleep(resp_headers, attempt)
                time.sleep(sleep_s)
                continue

            # Secondary rate limit often returns 403 with message.
            if status == 403 and is_secondary_rate_limit(data):
                sleep_s = compute_retry_sleep(resp_headers, attempt, default_s=60)
                time.sleep(sleep_s)
                continue

            if status >= 400:
                # Non-retryable HTTP error: return record (caller may stop) but we keep behavior
                # consistent with prior implementation: raise on non-retryable >= 400.
                raise RuntimeError(f"HTTP {status} for {url}")

            return record
        except Exception as e:
            last_error = e
            time.sleep(min(2**attempt, 60) + random.random())

    raise RuntimeError(f"Request failed after {max_retries} retries: {url}") from last_error


def read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def parse_curl_headers(path: str) -> dict:
    text = read_text_file(path)
    if not text:
        return {}
    # curl -D writes one or more header blocks (e.g., redirects). Choose the last non-empty block.
    # Normalize newlines.
    text = text.replace("\r\n", "\n")
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        return {}
    lines = blocks[-1].split("\n")
    headers = {}
    for line in lines[1:]:  # skip HTTP/1.1 200 OK
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip()] = v.strip()
    return headers


def compute_retry_sleep(headers: dict, attempt: int, default_s: int = 5) -> float:
    ra = headers.get("Retry-After") or headers.get("retry-after")
    if ra:
        try:
            return float(ra) + random.random()
        except ValueError:
            pass
    reset = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
    if reset and str(reset).isdigit():
        reset_ts = int(reset)
        now = int(time.time())
        if reset_ts > now:
            return float(min(reset_ts - now + 1, 60)) + random.random()
    return float(min(default_s * (2 ** (attempt - 1)), 60)) + random.random()


def is_secondary_rate_limit(data: dict) -> bool:
    msg = ""
    if isinstance(data, dict):
        msg = str(data.get("message") or "")
    return "secondary rate limit" in msg.lower()


def gh_headers(token: str) -> dict:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def rest_search_issues(*, token: str, q: str, per_page: int, out_dir: str, tag_prefix: str) -> list[dict]:
    results = []
    page = 1
    while True:
        params = {"q": q, "per_page": str(per_page), "page": str(page)}
        url = f"{GITHUB_API}/search/issues?{urllib.parse.urlencode(params)}"
        tag = f"{tag_prefix}_page{page}"
        rec = http_request_json(
            method="GET",
            url=url,
            headers=gh_headers(token),
            body_obj=None,
            timeout_s=60,
            max_retries=6,
            out_dir=out_dir,
            tag=tag,
        )
        data = rec["response"]["json"]
        items = data.get("items") or []
        results.extend(items)
        if len(items) < per_page:
            break
        page += 1
        if page > 100:
            # guard: GitHub search caps / needs refined query
            break
    return results


GET_CORE = """
query GetIssueOrPRCore($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        id
        databaseId
        number
        url
        title
        body
        state
        locked
        author {
          __typename
          login
          url
          avatarUrl
          ... on User { id databaseId }
          ... on Organization { id databaseId }
          ... on Bot { id databaseId }
          ... on Mannequin { id databaseId }
        }
        authorAssociation
        createdAt
        updatedAt
        closedAt
        labels(first: 100) { nodes { name color description } }
        milestone { title description dueOn state number }
        assignees(first: 100) { nodes { login id databaseId url avatarUrl __typename } }
        comments { totalCount }
      }
      ... on PullRequest {
        id
        databaseId
        number
        url
        title
        body
        state
        isDraft
        locked
        author {
          __typename
          login
          url
          avatarUrl
          ... on User { id databaseId }
          ... on Organization { id databaseId }
          ... on Bot { id databaseId }
          ... on Mannequin { id databaseId }
        }
        authorAssociation
        createdAt
        updatedAt
        closedAt
        mergedAt
        mergedBy {
          __typename
          login
          url
          avatarUrl
          ... on User { id databaseId }
          ... on Organization { id databaseId }
          ... on Bot { id databaseId }
          ... on Mannequin { id databaseId }
        }
        mergeCommit { oid url }
        baseRefName
        headRefName
        headRefOid
        additions
        deletions
        changedFiles
        labels(first: 100) { nodes { name color description } }
        milestone { title description dueOn state number }
        assignees(first: 100) { nodes { login id databaseId url avatarUrl __typename } }
        comments { totalCount }
        reviews { totalCount }
        files { totalCount }
      }
    }
  }
}
""".strip()


GET_COMMENTS_PAGE = """
query GetItemCommentsPage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        comments(first: 100, after: $after) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id
            databaseId
            url
            body
            createdAt
            updatedAt
            author {
              __typename
              login
              url
              avatarUrl
              ... on User { id databaseId }
              ... on Organization { id databaseId }
              ... on Bot { id databaseId }
              ... on Mannequin { id databaseId }
            }
            authorAssociation
          }
        }
      }
      ... on PullRequest {
        comments(first: 100, after: $after) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id
            databaseId
            url
            body
            createdAt
            updatedAt
            author {
              __typename
              login
              url
              avatarUrl
              ... on User { id databaseId }
              ... on Organization { id databaseId }
              ... on Bot { id databaseId }
              ... on Mannequin { id databaseId }
            }
            authorAssociation
          }
        }
      }
    }
  }
}
""".strip()


GET_TIMELINE_PAGE = """
query GetItemTimelinePage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        timelineItems(
          first: 100
          after: $after
          itemTypes: [
            CLOSED_EVENT, REOPENED_EVENT,
            LABELED_EVENT, UNLABELED_EVENT,
            ASSIGNED_EVENT, UNASSIGNED_EVENT,
            MILESTONED_EVENT, DEMILESTONED_EVENT,
            RENAMED_TITLE_EVENT,
            CROSS_REFERENCED_EVENT, REFERENCED_EVENT
          ]
        ) {
          pageInfo { hasNextPage endCursor }
          nodes {
            __typename
            ... on ClosedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
            }
            ... on ReopenedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
            }
            ... on LabeledEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              label { name color }
            }
            ... on UnlabeledEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              label { name color }
            }
            ... on AssignedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              assignee { __typename ... on User { login id id } }
            }
            ... on UnassignedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              assignee { __typename ... on User { login id id } }
            }
            ... on MilestonedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              milestoneTitle
            }
            ... on DemilestonedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              milestoneTitle
            }
            ... on RenamedTitleEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              previousTitle
              currentTitle
            }
            ... on CrossReferencedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              source {
                __typename
                ... on Issue { number url title }
                ... on PullRequest { number url title }
              }
            }
            ... on ReferencedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              commit { oid url }
              commitRepository { nameWithOwner }
            }
          }
        }
      }
      ... on PullRequest {
        timelineItems(
          first: 100
          after: $after
          itemTypes: [
            CLOSED_EVENT, REOPENED_EVENT,
            LABELED_EVENT, UNLABELED_EVENT,
            ASSIGNED_EVENT, UNASSIGNED_EVENT,
            MILESTONED_EVENT, DEMILESTONED_EVENT,
            RENAMED_TITLE_EVENT,
            CROSS_REFERENCED_EVENT, REFERENCED_EVENT
          ]
        ) {
          pageInfo { hasNextPage endCursor }
          nodes {
            __typename
            ... on ClosedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
            }
            ... on ReopenedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
            }
            ... on LabeledEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              label { name color }
            }
            ... on UnlabeledEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              label { name color }
            }
            ... on AssignedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              assignee { __typename ... on User { login id id } }
            }
            ... on UnassignedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              assignee { __typename ... on User { login id id } }
            }
            ... on MilestonedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              milestoneTitle
            }
            ... on DemilestonedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              milestoneTitle
            }
            ... on RenamedTitleEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              previousTitle
              currentTitle
            }
            ... on CrossReferencedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              source {
                __typename
                ... on Issue { number url title }
                ... on PullRequest { number url title }
              }
            }
            ... on ReferencedEvent {
              id
              createdAt
              actor {
                __typename
                login
                url
                avatarUrl
                ... on User { id databaseId }
                ... on Organization { id databaseId }
                ... on Bot { id databaseId }
                ... on Mannequin { id databaseId }
              }
              commit { oid url }
              commitRepository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
""".strip()


GET_PR_REVIEWS_PAGE = """
query GetPRReviewsPage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviews(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          databaseId
          author {
            __typename
            login
            url
            avatarUrl
            ... on User { id databaseId }
            ... on Organization { id databaseId }
            ... on Bot { id databaseId }
            ... on Mannequin { id databaseId }
          }
          state
          body
          submittedAt
        }
      }
    }
  }
}
""".strip()


GET_PR_FILES_PAGE = """
query GetPRFilesPage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      files(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          path
          additions
          deletions
          changeType
        }
      }
    }
  }
}
""".strip()


def graphql_call(*, token: str, query: str, variables: dict, out_dir: str, tag: str) -> dict:
    body = {"query": query, "variables": variables}
    rec = http_request_json(
        method="POST",
        url=GITHUB_GRAPHQL,
        headers=gh_headers(token),
        body_obj=body,
        timeout_s=90,
        max_retries=6,
        out_dir=out_dir,
        tag=tag,
    )
    payload = rec.get("response", {}).get("json")
    if isinstance(payload, dict) and payload.get("errors"):
        errors = payload.get("errors") or []
        first = errors[0] if isinstance(errors, list) and errors else {}
        message = first.get("message") if isinstance(first, dict) else None
        path = first.get("path") if isinstance(first, dict) else None
        raise RuntimeError(f"GraphQL returned {len(errors)} error(s). First: {message!r} path={path!r}")
    return rec


def paginate_connection(get_page_fn, *, max_pages: int = 1000) -> None:
    pages = 0
    after = None
    while True:
        pages += 1
        if pages > max_pages:
            raise RuntimeError("Pagination exceeded max_pages guard")
        rec = get_page_fn(after)
        data = rec["response"]["json"]
        # Caller knows where to look for pageInfo; we return it via a regex-based extractor below.
        page_info = extract_page_info(data)
        if not page_info:
            break
        has_next, end_cursor = page_info
        if not has_next or not end_cursor:
            break
        after = end_cursor


def extract_page_info(data: dict) -> tuple[bool, str] | None:
    """
    Minimal 'processing': locate the first {pageInfo:{hasNextPage,endCursor}} anywhere in the JSON.
    This is intentionally generic to avoid coupling to a specific response shape.
    """
    try:
        raw = json.dumps(data, ensure_ascii=False)
    except Exception:
        return None
    m = re.search(r'"pageInfo"\\s*:\\s*\\{[^}]*"hasNextPage"\\s*:\\s*(true|false)[^}]*"endCursor"\\s*:\\s*("([^"]*)"|null)', raw)
    if not m:
        return None
    has_next = m.group(1) == "true"
    end_cursor = m.group(3) or ""
    return (has_next, end_cursor)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query GitHub (closedAt window) and write raw responses locally.")
    p.add_argument("--owner", default="openai")
    p.add_argument("--repo", default="openai-agents-python")
    p.add_argument("--start", default="2026-01-06", help="YYYY-MM-DD (closedAt window start, UTC)")
    p.add_argument("--end", default="2026-01-20", help="YYYY-MM-DD (closedAt window end, UTC)")
    p.add_argument("--out", default=None, help="Output directory. Default: raw/{owner}-{repo}/closedAt_{start}_{end}_{ts}")
    p.add_argument("--per-page", type=int, default=100)
    p.add_argument("--max-items", type=int, default=0, help="If >0, limit number of items hydrated (for smoke runs).")
    p.add_argument("--no-hydrate", action="store_true", help="Only run discovery and save raw search responses.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token and not args.no_hydrate:
        print(
            "Missing GitHub token. Set env var GITHUB_TOKEN (recommended) or GH_TOKEN.\n"
            "Tip: You can run discovery-only without a token via --no-hydrate.",
            file=sys.stderr,
        )
        return 2

    owner = args.owner
    repo = args.repo
    start = args.start
    end = args.end

    if args.out:
        out_dir = args.out
    else:
        out_dir = os.path.join("raw", f"{owner}-{repo}", f"closedAt_{start}_{end}_{utc_now_compact()}")

    ensure_dir(out_dir)
    safe_write_json(
        os.path.join(out_dir, "run.json"),
        {
            "repo": f"{owner}/{repo}",
            "window": {"closedAt_start": start, "closedAt_end": end},
            "started_at": dt.datetime.utcnow().isoformat() + "Z",
            "notes": "Raw-only ingestion. No normalization or downstream processing performed.",
        },
    )

    q_pr = f"repo:{owner}/{repo} is:pr state:closed closed:{start}..{end}"
    q_issue = f"repo:{owner}/{repo} is:issue state:closed closed:{start}..{end}"

    pr_items = rest_search_issues(
        token=token, q=q_pr, per_page=args.per_page, out_dir=out_dir, tag_prefix="discovery_pr"
    )
    issue_items = rest_search_issues(
        token=token, q=q_issue, per_page=args.per_page, out_dir=out_dir, tag_prefix="discovery_issue"
    )

    # Save the discovered item list (still raw-ish; just a convenience index).
    discovered = {
        "repo": f"{owner}/{repo}",
        "window": {"closedAt_start": start, "closedAt_end": end},
        "discovery": {
            "pr_count": len(pr_items),
            "issue_count": len(issue_items),
            "prs": [{"number": it.get("number"), "url": it.get("html_url")} for it in pr_items],
            "issues": [{"number": it.get("number"), "url": it.get("html_url")} for it in issue_items],
        },
    }
    safe_write_json(os.path.join(out_dir, "discovered_index.json"), discovered)

    if args.no_hydrate:
        return 0

    numbers = [it.get("number") for it in pr_items + issue_items if isinstance(it.get("number"), int)]
    # deterministic order
    numbers = sorted(set(numbers))
    if args.max_items and args.max_items > 0:
        numbers = numbers[: args.max_items]

    variables_base = {"owner": owner, "name": repo}
    for n in numbers:
        tag = f"graphql_core_item{n}"
        rec = graphql_call(token=token, query=GET_CORE, variables={**variables_base, "number": n}, out_dir=out_dir, tag=tag)
        data = rec["response"]["json"]
        typename = (
            data.get("data", {})
            .get("repository", {})
            .get("issueOrPullRequest", {})
            .get("__typename")
        )

        def get_comments_page(after_cursor):
            t = f"graphql_comments_item{n}_p{sha256_hex(after_cursor or 'start')[:8]}"
            return graphql_call(
                token=token,
                query=GET_COMMENTS_PAGE,
                variables={**variables_base, "number": n, "after": after_cursor},
                out_dir=out_dir,
                tag=t,
            )

        paginate_connection(get_comments_page)

        def get_timeline_page(after_cursor):
            t = f"graphql_timeline_item{n}_p{sha256_hex(after_cursor or 'start')[:8]}"
            return graphql_call(
                token=token,
                query=GET_TIMELINE_PAGE,
                variables={**variables_base, "number": n, "after": after_cursor},
                out_dir=out_dir,
                tag=t,
            )

        paginate_connection(get_timeline_page)

        if typename == "PullRequest":
            def get_reviews_page(after_cursor):
                t = f"graphql_reviews_pr{n}_p{sha256_hex(after_cursor or 'start')[:8]}"
                return graphql_call(
                    token=token,
                    query=GET_PR_REVIEWS_PAGE,
                    variables={**variables_base, "number": n, "after": after_cursor},
                    out_dir=out_dir,
                    tag=t,
                )

            paginate_connection(get_reviews_page)

            def get_files_page(after_cursor):
                t = f"graphql_files_pr{n}_p{sha256_hex(after_cursor or 'start')[:8]}"
                return graphql_call(
                    token=token,
                    query=GET_PR_FILES_PAGE,
                    variables={**variables_base, "number": n, "after": after_cursor},
                    out_dir=out_dir,
                    tag=t,
                )

            paginate_connection(get_files_page)

            # REST: pulls/{n}/files for patch content (page-based)
            page = 1
            while True:
                url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{n}/files?per_page={args.per_page}&page={page}"
                tag = f"rest_pr_files_pr{n}_page{page}"
                rec = http_request_json(
                    method="GET",
                    url=url,
                    headers=gh_headers(token),
                    body_obj=None,
                    timeout_s=60,
                    max_retries=6,
                    out_dir=out_dir,
                    tag=tag,
                )
                items = (rec["response"]["json"] or [])
                if not isinstance(items, list) or len(items) < args.per_page:
                    break
                page += 1
                if page > 1000:
                    break

    safe_write_json(
        os.path.join(out_dir, "run_finished.json"),
        {"finished_at": dt.datetime.utcnow().isoformat() + "Z", "hydrated_item_count": len(numbers)},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
