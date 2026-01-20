#!/usr/bin/env python3
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import urllib.parse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build bounded repo_insights.json/.md from raw_http JSON records.")
    p.add_argument("--raw-http-dir", required=True, help="Path to raw_http directory (contains tag/ subdirs with *.json).")
    p.add_argument("--out-dir", default="out_insights", help="Output directory (default: out_insights).")
    p.add_argument("--max-cards", type=int, default=30, help="Maximum number of insight cards to emit.")
    p.add_argument("--max-evidence", type=int, default=5, help="Maximum evidence entries per card.")
    p.add_argument("--max-statement-chars", type=int, default=240, help="Maximum statement length per card.")
    p.add_argument("--max-body-chars", type=int, default=280, help="Max chars for body excerpts used in evidence.")
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


def safe_excerpt(text: str | None, *, max_chars: int) -> str:
    if not isinstance(text, str) or not text:
        return ""
    s = re.sub(r"\s+", " ", text).strip()
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 1)] + "…"


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


def shorten(text: str, max_chars: int) -> str:
    s = re.sub(r"\s+", " ", (text or "")).strip()
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 1)] + "…"


def is_maintainer_role(author_association: str) -> bool:
    return author_association in ("MEMBER", "OWNER", "COLLABORATOR")


def tokenize(text: str) -> list[str]:
    # Keep lightweight and stable. This is not a semantic tokenizer.
    return [t for t in re.split(r"[^A-Za-z0-9_./:-]+", (text or "").lower()) if t]


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "do",
    "for",
    "from",
    "get",
    "has",
    "have",
    "i",
    "if",
    "in",
    "is",
    "it",
    "just",
    "me",
    "my",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "please",
    "so",
    "that",
    "the",
    "this",
    "to",
    "try",
    "we",
    "what",
    "with",
    "you",
    "your",
}


def extract_signals_from_raw_http(
    *, raw_http_dir: str, max_body_chars: int
) -> tuple[str | None, dict[tuple[int, str], dict], list[dict], list[dict]]:
    """
    Returns:
      repo_full_name, work_items_by_key, maintainer_comments, timeline_events
    """
    repo_full_name: str | None = None
    work_items: dict[tuple[int, str], dict] = {}
    maintainer_comments: list[dict] = []
    timeline_events: list[dict] = []

    for path in iter_json_files(raw_http_dir):
        try:
            record = load_json(path)
        except Exception:
            continue
        repo = derive_repo_full_name(record)
        if repo_full_name is None and repo:
            repo_full_name = repo

        tag = (record.get("meta") or {}).get("tag") or ""
        resp = (record.get("response") or {}).get("json")
        if not isinstance(resp, dict):
            continue
        data = resp.get("data") or {}
        if not isinstance(data, dict):
            continue

        if isinstance(tag, str) and tag.startswith("graphql_core_item"):
            item = (data.get("repository") or {}).get("issueOrPullRequest") or {}
            if not isinstance(item, dict):
                continue
            typename = item.get("__typename")
            if typename not in ("Issue", "PullRequest"):
                continue
            number = item.get("number")
            if not isinstance(number, int):
                continue
            item_type = "pr" if typename == "PullRequest" else "issue"
            url = item.get("url") if isinstance(item.get("url"), str) else build_work_item_url(repo or "", item_type, number)
            labels = []
            for n in ((item.get("labels") or {}).get("nodes") or []):
                if isinstance(n, dict) and isinstance(n.get("name"), str) and n.get("name"):
                    labels.append(n["name"])
            work_items[(number, item_type)] = {
                "number": number,
                "type": item_type,
                "url": url,
                "title": item.get("title") if isinstance(item.get("title"), str) else "",
                "labels": sorted(set(labels)),
                "created_at": item.get("createdAt") if isinstance(item.get("createdAt"), str) else "",
                "closed_at": item.get("closedAt") if isinstance(item.get("closedAt"), str) else "",
                "is_merged": bool(item.get("mergedAt")) if item_type == "pr" else False,
            }
            continue

        if isinstance(tag, str) and tag.startswith("graphql_comments_item"):
            iorp = (data.get("repository") or {}).get("issueOrPullRequest") or {}
            if not isinstance(iorp, dict):
                continue
            typename = iorp.get("__typename")
            if typename not in ("Issue", "PullRequest"):
                continue
            number = derive_number(record)
            if number is None:
                continue
            item_type = "pr" if typename == "PullRequest" else "issue"
            ref = build_work_item_url(repo or "", item_type, number)

            comment_nodes = ((iorp.get("comments") or {}).get("nodes") or [])
            if not isinstance(comment_nodes, list):
                continue
            for c in comment_nodes:
                if not isinstance(c, dict):
                    continue
                assoc = c.get("authorAssociation") if isinstance(c.get("authorAssociation"), str) else ""
                if not is_maintainer_role(assoc):
                    continue
                created_at = c.get("createdAt") if isinstance(c.get("createdAt"), str) else ""
                author = actor_login(c.get("author") or {}) or ""
                body_excerpt = safe_excerpt(c.get("body"), max_chars=max_body_chars)
                maintainer_comments.append(
                    {
                        "number": number,
                        "type": item_type,
                        "reference": ref,
                        "created_at": created_at,
                        "author_login": author,
                        "author_association": assoc,
                        "body_excerpt": body_excerpt,
                    }
                )
            continue

        if isinstance(tag, str) and tag.startswith("graphql_timeline_item"):
            iorp = (data.get("repository") or {}).get("issueOrPullRequest") or {}
            if not isinstance(iorp, dict):
                continue
            typename = iorp.get("__typename")
            if typename not in ("Issue", "PullRequest"):
                continue
            number = derive_number(record)
            if number is None:
                continue
            item_type = "pr" if typename == "PullRequest" else "issue"
            ref = build_work_item_url(repo or "", item_type, number)
            timeline_nodes = ((iorp.get("timelineItems") or {}).get("nodes") or [])
            if not isinstance(timeline_nodes, list):
                continue
            for ev in timeline_nodes:
                if not isinstance(ev, dict):
                    continue
                ev_type = ev.get("__typename")
                if not isinstance(ev_type, str) or not ev_type:
                    continue
                created_at = ev.get("createdAt") if isinstance(ev.get("createdAt"), str) else ""
                actor = actor_login(ev.get("actor") or {}) or ""
                if not created_at:
                    continue
                timeline_events.append(
                    {
                        "number": number,
                        "type": item_type,
                        "reference": ref,
                        "event_type": ev_type,
                        "created_at": created_at,
                        "actor_login": actor,
                    }
                )
            continue

    return repo_full_name, work_items, maintainer_comments, timeline_events


def build_insight_cards(
    *,
    repo_full_name: str,
    work_items: dict[tuple[int, str], dict],
    maintainer_comments: list[dict],
    timeline_events: list[dict],
    max_cards: int,
    max_evidence: int,
    max_statement_chars: int,
) -> list[dict]:
    taxonomy_cards: list[dict] = []
    workflow_cards: list[dict] = []
    support_cards: list[dict] = []

    # 1) Label taxonomy (frequency)
    label_counts_issue: collections.Counter[str] = collections.Counter()
    label_counts_pr: collections.Counter[str] = collections.Counter()
    label_to_refs: dict[str, list[str]] = collections.defaultdict(list)

    for (_number, item_type), wi in work_items.items():
        labels = wi.get("labels") or []
        if not isinstance(labels, list):
            continue
        for lab in labels:
            if not isinstance(lab, str) or not lab:
                continue
            if item_type == "issue":
                label_counts_issue[lab] += 1
            else:
                label_counts_pr[lab] += 1
            if len(label_to_refs[lab]) < max_evidence:
                label_to_refs[lab].append(wi.get("url") or wi.get("reference") or "")

    for label, count in label_counts_issue.most_common(8):
        st = f"최근 Closed Issue에서 라벨 `{label}`가 자주 사용됨 (표본 {count}건)."
        taxonomy_cards.append(
            {
                "id": f"labels.issue.{label}",
                "type": "taxonomy",
                "statement": shorten(st, max_statement_chars),
                "confidence": "medium",
                "evidence": [{"url": u, "why": "label usage example"} for u in label_to_refs.get(label, []) if u][:max_evidence],
            }
        )
    for label, count in label_counts_pr.most_common(8):
        st = f"최근 Closed PR에서 라벨 `{label}`가 자주 사용됨 (표본 {count}건)."
        taxonomy_cards.append(
            {
                "id": f"labels.pr.{label}",
                "type": "taxonomy",
                "statement": shorten(st, max_statement_chars),
                "confidence": "medium",
                "evidence": [{"url": u, "why": "label usage example"} for u in label_to_refs.get(label, []) if u][:max_evidence],
            }
        )

    # 2) Label co-occurrence (top pairs)
    pair_counts: collections.Counter[tuple[str, str]] = collections.Counter()
    pair_to_refs: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for (_number, _item_type), wi in work_items.items():
        labs = wi.get("labels") or []
        if not isinstance(labs, list):
            continue
        uniq = sorted(set([l for l in labs if isinstance(l, str) and l]))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                pair = (uniq[i], uniq[j])
                pair_counts[pair] += 1
                if len(pair_to_refs[pair]) < max_evidence:
                    pair_to_refs[pair].append(wi.get("url") or "")

    for (a, b), count in pair_counts.most_common(6):
        st = f"라벨 `{a}` + `{b}`가 함께 붙는 경우가 관찰됨 (표본 {count}건)."
        taxonomy_cards.append(
            {
                "id": f"labels.pair.{a}+{b}",
                "type": "taxonomy",
                "statement": shorten(st, max_statement_chars),
                "confidence": "low" if count < 3 else "medium",
                "evidence": [{"url": u, "why": "co-occurrence example"} for u in pair_to_refs.get((a, b), []) if u][:max_evidence],
            }
        )

    # 3) Workflow: reopen rate
    reopened = 0
    closed = 0
    refs_reopened: list[str] = []
    ev_type_counts: collections.Counter[str] = collections.Counter()
    ev_type_to_refs: dict[str, list[str]] = collections.defaultdict(list)
    for ev in timeline_events:
        if not isinstance(ev, dict):
            continue
        ev_type = ev.get("event_type")
        ref = ev.get("reference")
        if isinstance(ev_type, str) and ev_type:
            ev_type_counts[ev_type] += 1
            if isinstance(ref, str) and ref and len(ev_type_to_refs[ev_type]) < max_evidence:
                ev_type_to_refs[ev_type].append(ref)
        if ev_type == "ClosedEvent":
            closed += 1
        elif ev_type == "ReopenedEvent":
            reopened += 1
            if isinstance(ref, str) and ref and len(refs_reopened) < max_evidence:
                refs_reopened.append(ref)
    if closed > 0 and reopened > 0:
        pct = (reopened / max(closed, 1)) * 100.0
        st = f"Closed 이후 Reopen 이벤트가 발생하는 케이스가 있음 (약 {pct:.1f}% 수준, 이벤트 기준)."
        workflow_cards.append(
            {
                "id": "workflow.reopen_rate",
                "type": "workflow",
                "statement": shorten(st, max_statement_chars),
                "confidence": "low",
                "evidence": [{"url": u, "why": "reopen example"} for u in refs_reopened[:max_evidence]],
            }
        )

    for ev_type, count in ev_type_counts.most_common(6):
        if ev_type in ("ClosedEvent", "ReopenedEvent"):
            continue
        st = f"타임라인에서 `{ev_type}`가 자주 등장함 (표본 {count}건)."
        workflow_cards.append(
            {
                "id": f"workflow.event.{ev_type}",
                "type": "workflow",
                "statement": shorten(st, max_statement_chars),
                "confidence": "low" if count < 5 else "medium",
                "evidence": [{"url": u, "why": f"{ev_type} example"} for u in (ev_type_to_refs.get(ev_type) or []) if u][:max_evidence],
            }
        )

    # 4) DevRel checklist keywords (from maintainer comments)
    token_counts: collections.Counter[str] = collections.Counter()
    token_to_refs: dict[str, list[str]] = collections.defaultdict(list)
    for c in maintainer_comments:
        body = c.get("body_excerpt") if isinstance(c, dict) else ""
        ref = c.get("reference") if isinstance(c, dict) else ""
        for t in tokenize(body):
            if len(t) < 3:
                continue
            if t in STOPWORDS:
                continue
            token_counts[t] += 1
            if isinstance(ref, str) and ref and len(token_to_refs[t]) < max_evidence:
                token_to_refs[t].append(ref)

    for tok, count in token_counts.most_common(12):
        st = f"maintainer 코멘트에서 `{tok}` 관련 요청/안내가 반복됨 (표본 {count}회)."
        support_cards.append(
            {
                "id": f"support.keyword.{tok}",
                "type": "support_checklist",
                "statement": shorten(st, max_statement_chars),
                "confidence": "low" if count < 3 else "medium",
                "evidence": [{"url": u, "why": f"keyword '{tok}' appears"} for u in token_to_refs.get(tok, []) if u][:max_evidence],
            }
        )

    def dedupe(items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for c in items:
            cid = c.get("id")
            if not isinstance(cid, str) or not cid:
                continue
            if cid in seen:
                continue
            seen.add(cid)
            c["repo_full_name"] = repo_full_name
            out.append(c)
        return out

    taxonomy_cards = dedupe(taxonomy_cards)
    workflow_cards = dedupe(workflow_cards)
    support_cards = dedupe(support_cards)

    # Sort within each type by confidence, then stable id.
    conf_rank = {"high": 0, "medium": 1, "low": 2}
    taxonomy_cards.sort(key=lambda c: (conf_rank.get(c.get("confidence"), 9), c.get("id", "")))
    workflow_cards.sort(key=lambda c: (conf_rank.get(c.get("confidence"), 9), c.get("id", "")))
    support_cards.sort(key=lambda c: (conf_rank.get(c.get("confidence"), 9), c.get("id", "")))

    # Type-balanced cap to avoid "taxonomy-only" outputs.
    if max_cards <= 0:
        return []
    quota_tax = max(1, int(max_cards * 0.6))
    quota_work = max(1, int(max_cards * 0.2))
    quota_support = max(1, max_cards - quota_tax - quota_work)

    selected: list[dict] = []
    selected.extend(taxonomy_cards[:quota_tax])
    selected.extend(workflow_cards[:quota_work])
    selected.extend(support_cards[:quota_support])

    # Fill remaining slots (if any) from leftovers in a stable order.
    if len(selected) < max_cards:
        leftovers = taxonomy_cards[quota_tax:] + workflow_cards[quota_work:] + support_cards[quota_support:]
        # Prefer higher confidence, regardless of type, for fill.
        leftovers.sort(key=lambda c: (conf_rank.get(c.get("confidence"), 9), str(c.get("type") or ""), c.get("id", "")))
        for c in leftovers:
            if len(selected) >= max_cards:
                break
            selected.append(c)

    # Final stable order: taxonomy, workflow, support.
    type_rank = {"taxonomy": 0, "workflow": 1, "support_checklist": 2}
    selected.sort(key=lambda c: (type_rank.get(c.get("type"), 9), conf_rank.get(c.get("confidence"), 9), c.get("id", "")))
    return selected[:max_cards]


def render_insights_md(cards: list[dict]) -> str:
    lines = ["# repo_insights (bounded)", ""]
    by_type: dict[str, list[dict]] = collections.defaultdict(list)
    for c in cards:
        by_type[str(c.get("type") or "other")].append(c)
    for t in sorted(by_type.keys()):
        lines.append(f"## {t}")
        for c in by_type[t]:
            lines.append(f"- {c.get('statement')}")
            for ev in (c.get("evidence") or [])[:5]:
                if isinstance(ev, dict) and isinstance(ev.get("url"), str) and ev.get("url"):
                    why = ev.get("why") if isinstance(ev.get("why"), str) else ""
                    lines.append(f"  - {ev['url']}" + (f" — {why}" if why else ""))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    raw_http_dir = args.raw_http_dir
    out_dir = args.out_dir

    if not os.path.isdir(raw_http_dir):
        print(f"raw_http dir not found: {raw_http_dir}", file=sys.stderr)
        return 2

    ensure_dir(out_dir)

    repo_full_name, work_items, maintainer_comments, timeline_events = extract_signals_from_raw_http(
        raw_http_dir=raw_http_dir,
        max_body_chars=args.max_body_chars,
    )
    if not repo_full_name:
        repo_full_name = "unknown/unknown"

    cards = build_insight_cards(
        repo_full_name=repo_full_name,
        work_items=work_items,
        maintainer_comments=maintainer_comments,
        timeline_events=timeline_events,
        max_cards=args.max_cards,
        max_evidence=args.max_evidence,
        max_statement_chars=args.max_statement_chars,
    )

    payload = {
        "repo_full_name": repo_full_name,
        "generated_at_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "card_count": len(cards),
        "cards": cards,
        "notes": {
            "bounded_context": True,
            "statement_max_chars": args.max_statement_chars,
            "max_cards": args.max_cards,
            "max_evidence": args.max_evidence,
            "comment_body_excerpt_max_chars": args.max_body_chars,
        },
    }

    p_json = os.path.join(out_dir, "repo_insights.json")
    p_md = os.path.join(out_dir, "repo_insights.md")
    with open(p_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    with open(p_md, "w", encoding="utf-8") as f:
        f.write(render_insights_md(cards))

    print(f"Wrote {p_json}")
    print(f"Wrote {p_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
