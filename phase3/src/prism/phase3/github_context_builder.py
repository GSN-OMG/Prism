from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Mapping

from prism.env import load_dotenv

from .github_client import GitHubClient

GitHubType = Literal["issue", "pull_request"]


@dataclass(frozen=True, slots=True)
class AgentMapEntry:
    id: str
    role: str | None = None
    name: str | None = None


def _parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid repo: {repo} (expected owner/repo)")
    return parts[0], parts[1]


def _parse_iso_dt(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_within_range(ts: str, since: datetime | None, until: datetime | None) -> bool:
    try:
        dt = _parse_iso_dt(ts)
    except ValueError:
        return False
    if since and dt < since:
        return False
    if until and dt > until:
        return False
    return True


def _event_id(prefix: str, value: Any) -> str:
    return f"gh-{prefix}-{value}"


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _sanitize_sensitive_text(text: str) -> str:
    # Best-effort: do not leak auth headers/tokens via error strings.
    # Full redaction is enforced downstream before storage.
    import re

    out = text
    out = re.sub(r"\bgithub_pat_[A-Za-z0-9_]+\b", "***REDACTED:GITHUB_TOKEN***", out)
    out = re.sub(r"\bgh[pousr]_[A-Za-z0-9_]+\b", "***REDACTED:GITHUB_TOKEN***", out)
    out = re.sub(r"\bsk-proj-[A-Za-z0-9_-]+\b", "***REDACTED:OPENAI_API_KEY***", out)
    out = re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "***REDACTED:OPENAI_API_KEY***", out)
    return out


def _build_actor(
    *,
    login: str,
    user_type: str | None,
    agent_map: dict[str, AgentMapEntry] | None,
) -> tuple[str, str, str | None, dict[str, Any]]:
    mapped = agent_map.get(login) if agent_map else None
    if mapped is not None:
        return (
            "ai",
            mapped.id or login,
            mapped.role,
            {"github": {"actor_login": login}},
        )

    if user_type == "Bot":
        return ("system", login, None, {"github": {"actor_login": login}})

    return ("human", login, None, {"github": {"actor_login": login}})


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(ev: dict[str, Any]) -> tuple[int, float, int]:
        ts = ev.get("ts")
        if isinstance(ts, str) and ts:
            try:
                return (0, _parse_iso_dt(ts).timestamp(), 0)
            except ValueError:
                return (0, 0.0, 0)
        seq = ev.get("seq")
        return (1, 0.0, int(seq) if isinstance(seq, int) else 0)

    return sorted(events, key=key)


def _time_diff_sec(earlier: str | None, later: str | None) -> int | None:
    if not earlier or not later:
        return None
    try:
        a = _parse_iso_dt(earlier)
        b = _parse_iso_dt(later)
    except ValueError:
        return None
    if b < a:
        return None
    return int((b - a).total_seconds())


def _is_ci_failure(conclusion: Any) -> bool:
    value = str(conclusion or "").lower()
    return value in {
        "failure",
        "cancelled",
        "timed_out",
        "action_required",
        "startup_failure",
    }


def _issue_event_content(raw: Mapping[str, Any]) -> str:
    event = str(raw.get("event") or "event")
    if event == "labeled":
        label = raw.get("label") or {}
        name = label.get("name")
        return f"labeled: {name}" if name else "labeled"
    if event == "unlabeled":
        label = raw.get("label") or {}
        name = label.get("name")
        return f"unlabeled: {name}" if name else "unlabeled"
    if event == "assigned":
        assignee = raw.get("assignee") or {}
        login = assignee.get("login")
        return f"assigned: {login}" if login else "assigned"
    if event == "unassigned":
        assignee = raw.get("assignee") or {}
        login = assignee.get("login")
        return f"unassigned: {login}" if login else "unassigned"
    return event


def _parse_agent_map(raw: str | None) -> dict[str, AgentMapEntry] | None:
    if not raw:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("GITHUB_AGENT_MAP must be a JSON object")
    out: dict[str, AgentMapEntry] = {}
    for login, entry in parsed.items():
        if not isinstance(login, str) or not login:
            continue
        if not isinstance(entry, dict):
            continue
        agent_id = entry.get("id")
        if not isinstance(agent_id, str) or not agent_id:
            continue
        out[login] = AgentMapEntry(
            id=agent_id,
            role=entry.get("role") if isinstance(entry.get("role"), str) else None,
            name=entry.get("name") if isinstance(entry.get("name"), str) else None,
        )
    return out


def build_github_context_bundle(
    *,
    repo: str,
    type: GitHubType,
    number: int,
    token: str | None = None,
    base_url: str = "https://api.github.com",
    max_pages: int = 10,
    since: str | None = None,
    until: str | None = None,
    agent_map_json: str | None = None,
    include_files: bool = True,
    include_check_runs: bool = True,
    client: GitHubClient | None = None,
) -> dict[str, Any]:
    owner, repo_name = _parse_repo(repo)
    since_dt = _parse_iso_dt(since) if since else None
    until_dt = _parse_iso_dt(until) if until else None
    agent_map = _parse_agent_map(agent_map_json)

    gh = client or GitHubClient(token=token, base_url=base_url)
    events: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    bundle: dict[str, Any] = {
        "version": "0.1",
        "source": {"system": "github", "repo": f"{owner}/{repo_name}", "tags": [type]},
        "metadata": {"github": {"type": type, "number": number}},
        "agents": [],
        "result": {"status": "partial", "summary": "", "metrics": {}, "artifacts": []},
        "feedback": {"summary": "", "items": []},
        "events": [],
    }

    def record_error(exc: Exception, *, stage: str) -> None:
        message = _sanitize_sensitive_text(str(exc))
        events.append(
            {
                "id": _event_id("error", uuid.uuid4()),
                "ts": _now_utc_iso(),
                "actor_type": "system",
                "actor_id": "github_context_builder",
                "event_type": "error",
                "content": message,
                "meta": {
                    "stage": stage,
                    "github": {
                        "rate_limit": gh.last_rate_limit.to_dict()
                        if gh.last_rate_limit
                        else None
                    },
                },
            }
        )

    def safe(call: Any, *, stage: str) -> Any:
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - boundary: include error as evidence
            record_error(exc, stage=stage)
            return None

    issue = safe(
        lambda: gh.request_json(f"/repos/{owner}/{repo_name}/issues/{number}"),
        stage="fetch_issue",
    )
    if not isinstance(issue, dict):
        bundle["result"] = {
            "status": "failure",
            "summary": "Failed to fetch GitHub issue/PR",
            "metrics": {"rate_limit_events": gh.rate_limit_events},
            "artifacts": [],
        }
        bundle["events"] = _sort_events(events)
        return bundle

    pr: dict[str, Any] | None = None
    if type == "pull_request":
        pr = safe(
            lambda: gh.request_json(f"/repos/{owner}/{repo_name}/pulls/{number}"),
            stage="fetch_pull_request",
        )
        if pr is not None and not isinstance(pr, dict):
            pr = None

    github_url = issue.get("html_url") or (pr.get("html_url") if pr else None)
    title = str(issue.get("title") or (pr.get("title") if pr else "") or "")
    labels_raw = issue.get("labels") or []
    labels: list[str] = []
    if isinstance(labels_raw, list):
        for item in labels_raw:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                labels.append(item["name"])

    assignees_raw = issue.get("assignees") or []
    assignees: list[str] = []
    if isinstance(assignees_raw, list):
        for item in assignees_raw:
            if isinstance(item, dict) and isinstance(item.get("login"), str):
                assignees.append(item["login"])

    author_login = None
    author_type = None
    user_raw = issue.get("user") or {}
    if isinstance(user_raw, dict):
        author_login = (
            user_raw.get("login") if isinstance(user_raw.get("login"), str) else None
        )
        author_type = (
            user_raw.get("type") if isinstance(user_raw.get("type"), str) else None
        )

    state: str | None
    if type == "pull_request":
        merged_at = pr.get("merged_at") if pr else None
        if merged_at:
            state = "merged"
        else:
            state = (pr.get("state") if pr else None) or issue.get("state")
    else:
        state = issue.get("state")
    state = str(state) if state is not None else None

    bundle["metadata"]["github"] = {
        "type": type,
        "number": number,
        "url": github_url,
        "state": state,
        "title": title,
        "labels": labels,
        "assignees": assignees,
        "author": author_login,
    }

    opened_ts = issue.get("created_at") or (pr.get("created_at") if pr else None)
    closed_ts = issue.get("closed_at") or (pr.get("closed_at") if pr else None)
    merged_ts = pr.get("merged_at") if pr else None

    actor_type, actor_id, role, actor_meta = _build_actor(
        login=author_login or "unknown",
        user_type=author_type,
        agent_map=agent_map,
    )
    events.append(
        {
            "id": _event_id(
                "pr" if type == "pull_request" else "issue", issue.get("id") or number
            ),
            "ts": opened_ts,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "role": role,
            "event_type": "github.pull_request.opened"
            if type == "pull_request"
            else "github.issue.opened",
            "content": f"Opened {'PR' if type == 'pull_request' else 'Issue'} #{number}: {title}".strip(),
            "meta": {
                **actor_meta,
                "github": {**actor_meta.get("github", {}), "url": github_url},
            },
        }
    )

    issue_events = safe(
        lambda: gh.paginate(
            f"/repos/{owner}/{repo_name}/issues/{number}/events", max_pages=max_pages
        ),
        stage="fetch_issue_events",
    )
    if isinstance(issue_events, list):
        for ev in issue_events:
            if not isinstance(ev, dict):
                continue
            created_at = ev.get("created_at")
            if not isinstance(created_at, str) or not _is_within_range(
                created_at, since_dt, until_dt
            ):
                continue
            actor_raw = ev.get("actor") or {}
            actor_login = (
                actor_raw.get("login") if isinstance(actor_raw, dict) else None
            )
            actor_login = actor_login if isinstance(actor_login, str) else "unknown"
            actor_user_type = (
                actor_raw.get("type") if isinstance(actor_raw, dict) else None
            )
            actor_user_type = (
                actor_user_type if isinstance(actor_user_type, str) else None
            )
            ev_actor_type, ev_actor_id, ev_role, ev_actor_meta = _build_actor(
                login=actor_login,
                user_type=actor_user_type,
                agent_map=agent_map,
            )
            base = "github.pull_request" if type == "pull_request" else "github.issue"
            event_name = str(ev.get("event") or "event")
            events.append(
                {
                    "id": _event_id(
                        "issue_event", ev.get("id") or f"{event_name}-{created_at}"
                    ),
                    "ts": created_at,
                    "actor_type": ev_actor_type,
                    "actor_id": ev_actor_id,
                    "role": ev_role,
                    "event_type": f"{base}.{event_name}",
                    "content": _issue_event_content(ev),
                    "meta": {
                        **ev_actor_meta,
                        "github": {
                            **ev_actor_meta.get("github", {}),
                            "issue_event_id": ev.get("id"),
                            "url": github_url,
                        },
                    },
                }
            )

    issue_comments = safe(
        lambda: gh.paginate(
            f"/repos/{owner}/{repo_name}/issues/{number}/comments",
            max_pages=max_pages,
        ),
        stage="fetch_issue_comments",
    )
    if isinstance(issue_comments, list):
        for comment in issue_comments:
            if not isinstance(comment, dict):
                continue
            created_at = comment.get("created_at")
            if not isinstance(created_at, str) or not _is_within_range(
                created_at, since_dt, until_dt
            ):
                continue
            actor_raw = comment.get("user") or {}
            actor_login = (
                actor_raw.get("login") if isinstance(actor_raw, dict) else None
            )
            actor_login = actor_login if isinstance(actor_login, str) else "unknown"
            actor_user_type = (
                actor_raw.get("type") if isinstance(actor_raw, dict) else None
            )
            actor_user_type = (
                actor_user_type if isinstance(actor_user_type, str) else None
            )
            c_actor_type, c_actor_id, c_role, c_actor_meta = _build_actor(
                login=actor_login,
                user_type=actor_user_type,
                agent_map=agent_map,
            )
            events.append(
                {
                    "id": _event_id("issue_comment", comment.get("id") or created_at),
                    "ts": created_at,
                    "actor_type": c_actor_type,
                    "actor_id": c_actor_id,
                    "role": c_role,
                    "event_type": "github.pull_request.comment.created"
                    if type == "pull_request"
                    else "github.issue.comment.created",
                    "content": str(comment.get("body") or ""),
                    "meta": {
                        **c_actor_meta,
                        "github": {
                            **c_actor_meta.get("github", {}),
                            "comment_id": comment.get("id"),
                            "url": comment.get("html_url") or github_url,
                        },
                    },
                }
            )

    reviews: list[dict[str, Any]] | None = None
    review_comments: list[dict[str, Any]] | None = None
    check_runs: list[dict[str, Any]] | None = None

    if type == "pull_request" and pr is not None:
        reviews_raw = safe(
            lambda: gh.paginate(
                f"/repos/{owner}/{repo_name}/pulls/{number}/reviews",
                max_pages=max_pages,
            ),
            stage="fetch_reviews",
        )
        if isinstance(reviews_raw, list):
            reviews = [r for r in reviews_raw if isinstance(r, dict)]
            for review in reviews:
                ts = review.get("submitted_at") or review.get("created_at")
                if not isinstance(ts, str) or not _is_within_range(
                    ts, since_dt, until_dt
                ):
                    continue
                actor_raw = review.get("user") or {}
                actor_login = (
                    actor_raw.get("login") if isinstance(actor_raw, dict) else None
                )
                actor_login = actor_login if isinstance(actor_login, str) else "unknown"
                actor_user_type = (
                    actor_raw.get("type") if isinstance(actor_raw, dict) else None
                )
                actor_user_type = (
                    actor_user_type if isinstance(actor_user_type, str) else None
                )
                r_actor_type, r_actor_id, r_role, r_actor_meta = _build_actor(
                    login=actor_login,
                    user_type=actor_user_type,
                    agent_map=agent_map,
                )
                state_value = review.get("state")
                state_lower = str(state_value or "").lower()
                body = str(review.get("body") or "")
                content = body or (
                    f"Review submitted: {state_lower}"
                    if state_lower
                    else "Review submitted"
                )
                events.append(
                    {
                        "id": _event_id("review", review.get("id") or ts),
                        "ts": ts,
                        "actor_type": r_actor_type,
                        "actor_id": r_actor_id,
                        "role": r_role,
                        "event_type": "github.review.submitted",
                        "content": content,
                        "meta": {
                            **r_actor_meta,
                            "github": {
                                **r_actor_meta.get("github", {}),
                                "pull_request_number": number,
                                "review_id": review.get("id"),
                                "review_state": state_value,
                                "url": review.get("html_url") or github_url,
                            },
                        },
                    }
                )

        review_comments_raw = safe(
            lambda: gh.paginate(
                f"/repos/{owner}/{repo_name}/pulls/{number}/comments",
                max_pages=max_pages,
            ),
            stage="fetch_review_comments",
        )
        if isinstance(review_comments_raw, list):
            review_comments = [c for c in review_comments_raw if isinstance(c, dict)]
            for comment in review_comments:
                created_at = comment.get("created_at")
                if not isinstance(created_at, str) or not _is_within_range(
                    created_at, since_dt, until_dt
                ):
                    continue
                actor_raw = comment.get("user") or {}
                actor_login = (
                    actor_raw.get("login") if isinstance(actor_raw, dict) else None
                )
                actor_login = actor_login if isinstance(actor_login, str) else "unknown"
                actor_user_type = (
                    actor_raw.get("type") if isinstance(actor_raw, dict) else None
                )
                actor_user_type = (
                    actor_user_type if isinstance(actor_user_type, str) else None
                )
                rc_actor_type, rc_actor_id, rc_role, rc_actor_meta = _build_actor(
                    login=actor_login,
                    user_type=actor_user_type,
                    agent_map=agent_map,
                )
                events.append(
                    {
                        "id": _event_id(
                            "review_comment", comment.get("id") or created_at
                        ),
                        "ts": created_at,
                        "actor_type": rc_actor_type,
                        "actor_id": rc_actor_id,
                        "role": rc_role,
                        "event_type": "github.review.comment.created",
                        "content": str(comment.get("body") or ""),
                        "meta": {
                            **rc_actor_meta,
                            "github": {
                                **rc_actor_meta.get("github", {}),
                                "pull_request_number": number,
                                "review_comment_id": comment.get("id"),
                                "url": comment.get("html_url") or github_url,
                                "path": comment.get("path"),
                                "position": comment.get("position"),
                                "commit_id": comment.get("commit_id"),
                            },
                        },
                    }
                )

        if include_files:
            files_raw = safe(
                lambda: gh.paginate(
                    f"/repos/{owner}/{repo_name}/pulls/{number}/files",
                    max_pages=max_pages,
                ),
                stage="fetch_pull_request_files",
            )
            if isinstance(files_raw, list):
                files = [f for f in files_raw if isinstance(f, dict)]
                artifacts.append(
                    {
                        "type": "github.pull_request.files",
                        "url": f"{github_url}/files" if github_url else None,
                        "count": len(files),
                        "files": [
                            {
                                "filename": f.get("filename"),
                                "status": f.get("status"),
                                "additions": _safe_int(f.get("additions")),
                                "deletions": _safe_int(f.get("deletions")),
                                "changes": _safe_int(f.get("changes")),
                            }
                            for f in files
                            if isinstance(f.get("filename"), str)
                        ],
                    }
                )

        if include_check_runs:
            head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
            head_sha = head.get("sha") if isinstance(head.get("sha"), str) else None
            if head_sha:
                checks = safe(
                    lambda: gh.request_json(
                        f"/repos/{owner}/{repo_name}/commits/{head_sha}/check-runs",
                        query={"per_page": 100},
                    ),
                    stage="fetch_check_runs",
                )
                if isinstance(checks, dict) and isinstance(
                    checks.get("check_runs"), list
                ):
                    check_runs = [
                        r for r in checks["check_runs"] if isinstance(r, dict)
                    ]
                    for run in check_runs:
                        completed_at = run.get("completed_at")
                        if not isinstance(completed_at, str) or not _is_within_range(
                            completed_at, since_dt, until_dt
                        ):
                            continue
                        conclusion = (
                            run.get("conclusion") or run.get("status") or "unknown"
                        )
                        events.append(
                            {
                                "id": _event_id(
                                    "check_run",
                                    run.get("id") or completed_at or run.get("name"),
                                ),
                                "ts": completed_at,
                                "actor_type": "system",
                                "actor_id": "github",
                                "event_type": "github.ci.check_run.completed",
                                "content": f"{run.get('name') or 'check'}: {conclusion}",
                                "usage": {
                                    "rate_limit_remaining": gh.last_rate_limit.remaining
                                    if gh.last_rate_limit
                                    else None,
                                    "rate_limit_reset_at": gh.last_rate_limit.reset_at
                                    if gh.last_rate_limit
                                    else None,
                                },
                                "meta": {
                                    "github": {
                                        "check_run_id": run.get("id"),
                                        "pull_request_number": number,
                                        "url": run.get("details_url") or github_url,
                                        "conclusion": run.get("conclusion"),
                                        "status": run.get("status"),
                                    }
                                },
                            }
                        )

    filtered_events = [
        e
        for e in events
        if not e.get("ts") or _is_within_range(e["ts"], since_dt, until_dt)
    ]  # type: ignore[index]
    filtered_events = _sort_events(filtered_events)

    metrics: dict[str, Any] = {"rate_limit_events": gh.rate_limit_events}
    if isinstance(opened_ts, str):
        if type == "pull_request" and isinstance(merged_ts, str):
            metrics["time_to_merge_sec"] = _time_diff_sec(opened_ts, merged_ts)
        if isinstance(closed_ts, str):
            metrics["time_to_close_sec"] = _time_diff_sec(opened_ts, closed_ts)

        first_candidates: list[str] = []
        if isinstance(issue_comments, list):
            for c in issue_comments:
                if not isinstance(c, dict):
                    continue
                ts = c.get("created_at")
                if not isinstance(ts, str) or not _is_within_range(
                    ts, since_dt, until_dt
                ):
                    continue
                user = c.get("user") if isinstance(c.get("user"), dict) else {}
                if author_login and user.get("login") == author_login:
                    continue
                if user.get("type") == "Bot":
                    continue
                first_candidates.append(ts)
        if reviews:
            for r in reviews:
                ts = r.get("submitted_at") or r.get("created_at")
                if not isinstance(ts, str) or not _is_within_range(
                    ts, since_dt, until_dt
                ):
                    continue
                user = r.get("user") if isinstance(r.get("user"), dict) else {}
                if author_login and user.get("login") == author_login:
                    continue
                if user.get("type") == "Bot":
                    continue
                first_candidates.append(ts)
        if review_comments:
            for c in review_comments:
                ts = c.get("created_at")
                if not isinstance(ts, str) or not _is_within_range(
                    ts, since_dt, until_dt
                ):
                    continue
                user = c.get("user") if isinstance(c.get("user"), dict) else {}
                if author_login and user.get("login") == author_login:
                    continue
                if user.get("type") == "Bot":
                    continue
                first_candidates.append(ts)
        if first_candidates:
            first_candidates.sort(key=lambda s: _parse_iso_dt(s))
            metrics["time_to_first_response_sec"] = _time_diff_sec(
                opened_ts, first_candidates[0]
            )

    metrics["num_comments"] = (
        len(issue_comments) if isinstance(issue_comments, list) else 0
    )
    metrics["num_review_comments"] = (
        len(review_comments) if isinstance(review_comments, list) else 0
    )
    metrics["num_review_roundtrips"] = (
        max(0, len(reviews) - 1) if reviews is not None else 0
    )

    if check_runs is not None:
        metrics["num_ci_failures"] = sum(
            1 for r in check_runs if _is_ci_failure(r.get("conclusion"))
        )
        counts: dict[str, int] = {}
        for r in check_runs:
            name = r.get("name")
            if isinstance(name, str) and name:
                counts[name] = counts.get(name, 0) + 1
        metrics["num_ci_retries"] = sum(max(0, c - 1) for c in counts.values())

    involved_agents: dict[str, dict[str, Any]] = {}
    if agent_map:
        for ev in filtered_events:
            actor_login = ev.get("meta", {}).get("github", {}).get("actor_login")  # type: ignore[union-attr]
            if not isinstance(actor_login, str):
                continue
            mapped = agent_map.get(actor_login)
            if not mapped:
                continue
            involved_agents[mapped.id] = {
                "id": mapped.id,
                "name": mapped.name,
                "role": mapped.role,
                "meta": {"github": {"login": actor_login}},
            }

    if type == "pull_request":
        if state == "merged":
            status = "success"
            summary = "PR merged"
        elif state == "closed":
            status = "failure"
            summary = "PR closed"
        else:
            status = "partial"
            summary = "PR open"
    else:
        if state == "closed":
            status = "success"
            summary = "Issue closed"
        else:
            status = "partial"
            summary = "Issue open"

    bundle["agents"] = list(involved_agents.values())
    bundle["result"] = {
        "status": status,
        "summary": summary,
        "metrics": metrics,
        "artifacts": artifacts,
    }
    bundle["events"] = filtered_events
    return bundle


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw not in {"0", "false", "False", "no", "NO"}


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="GitHub Issue/PR -> ContextBundle builder"
    )
    parser.add_argument("--out", help="write JSON to a file instead of stdout")
    args = parser.parse_args(argv)

    repo = os.environ.get("GITHUB_REPO")
    gh_type = os.environ.get("GITHUB_TYPE")
    number_raw = os.environ.get("GITHUB_NUMBER")

    if not repo:
        raise SystemExit("Missing env var: GITHUB_REPO (owner/repo)")
    if gh_type not in ("issue", "pull_request"):
        raise SystemExit("Invalid env var: GITHUB_TYPE (issue|pull_request)")
    if not number_raw:
        raise SystemExit("Missing env var: GITHUB_NUMBER")
    number = int(number_raw)

    bundle = build_github_context_bundle(
        repo=repo,
        type=gh_type,
        number=number,
        token=os.environ.get("GITHUB_TOKEN"),
        base_url=os.environ.get("GITHUB_BASE_URL", "https://api.github.com"),
        max_pages=int(os.environ.get("GITHUB_MAX_PAGES", "10")),
        since=os.environ.get("GITHUB_SINCE"),
        until=os.environ.get("GITHUB_UNTIL"),
        agent_map_json=os.environ.get("GITHUB_AGENT_MAP"),
        include_files=_parse_bool_env("GITHUB_INCLUDE_FILES", True),
        include_check_runs=_parse_bool_env("GITHUB_INCLUDE_CHECK_RUNS", True),
    )

    out = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
