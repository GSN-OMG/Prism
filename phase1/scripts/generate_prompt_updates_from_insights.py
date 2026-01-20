#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate per-agent system prompt drafts from AGENTS_SUMMARY.md + repo_insights.json.")
    p.add_argument("--agents-summary", required=True, help="Path to AGENTS_SUMMARY.md.")
    p.add_argument("--repo-insights", required=True, help="Path to out_insights/repo_insights.json.")
    p.add_argument("--out-dir", default="out_prompts", help="Output directory (default: out_prompts).")
    p.add_argument("--max-cards-per-agent", type=int, default=15, help="Max insight cards to inject per agent.")
    p.add_argument("--language", default="ko", choices=["ko", "en"], help="Language for injected context block.")
    p.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), help="OpenAI model (default: env OPENAI_MODEL or gpt-4o-mini).")
    p.add_argument("--temperature", type=float, default=0.0, help="LLM temperature (default: 0.0).")
    p.add_argument("--max-output-tokens", type=int, default=1400, help="LLM max output tokens (default: 1400).")
    p.add_argument("--timeout-seconds", type=float, default=90.0, help="HTTP timeout seconds (default: 90).")
    return p.parse_args()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def slugify_agent_id(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^A-Za-z0-9_.:-]+", "", s)
    return s or "agent"


def parse_agents_summary(md_text: str) -> list[dict]:
    """
    Minimal parser for the recommended format in docs/openai-agents-python-prompt-refiner-agent-spec.md.

    Expected per-agent section:
      ## <agent_id>
      Purpose: ...
      Current System Prompt:
      ```...```
    """
    agents: list[dict] = []
    # Split on level-2 headings.
    parts = re.split(r"(?m)^##\s+", md_text)
    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        agent_id = lines[0].strip()
        if not agent_id:
            continue

        purpose = ""
        m_purpose = re.search(r"(?mi)^Purpose:\s*(.+)$", part)
        if m_purpose:
            purpose = m_purpose.group(1).strip()

        # Find the first fenced code block after "Current System Prompt:"
        prompt = ""
        m = re.search(r"(?ms)^Current System Prompt:\s*\n```.*?\n(.*?)\n```\s*$", part)
        if not m:
            m = re.search(r"(?ms)^Current System Prompt:\s*\n```.*?\n(.*?)\n```", part)
        if m:
            prompt = m.group(1).rstrip()

        agents.append({"agent_id": agent_id, "purpose": purpose, "current_system_prompt": prompt})
    return agents


def select_cards_for_agent(cards: list[dict], *, purpose: str, max_cards: int) -> list[dict]:
    # v0 heuristic: include top-N, plus boost cards that match purpose keywords.
    purpose_tokens = set([t for t in re.split(r"[^A-Za-z0-9_]+", (purpose or "").lower()) if t])
    boosted: list[tuple[int, dict]] = []
    for idx, c in enumerate(cards):
        statement = str(c.get("statement") or "").lower()
        score = 0
        for t in purpose_tokens:
            if t and t in statement:
                score += 3
        ctype = str(c.get("type") or "")
        if "devrel" in purpose_tokens and ctype in ("support_checklist", "workflow"):
            score += 2
        boosted.append((-(score), idx, c))
    boosted.sort()
    selected = [c for _neg, _idx, c in boosted][:max_cards]
    return selected


def render_injected_block(cards: list[dict], *, repo_full_name: str, language: str) -> str:
    if language == "en":
        header = "Repo-Specific Context (evidence-based, bounded)"
        lead = f"- Target repo: {repo_full_name}"
        rule = "- Prefer these rules over generic advice when they apply."
    else:
        header = "Repo-Specific Context (증거 기반, bounded)"
        lead = f"- 대상 레포: {repo_full_name}"
        rule = "- 일반론보다 아래 관찰/규칙을 우선 적용(해당되는 경우)."

    lines = [header, lead, rule, "- Insights:"]
    for c in cards:
        st = str(c.get("statement") or "").strip()
        if not st:
            continue
        lines.append(f"  - {st}")
        evs = c.get("evidence") or []
        if isinstance(evs, list) and evs:
            # Keep evidence compact: URLs only.
            urls = []
            for ev in evs[:3]:
                if isinstance(ev, dict) and isinstance(ev.get("url"), str) and ev.get("url"):
                    urls.append(ev["url"])
            if urls:
                lines.append("    - Evidence: " + ", ".join(urls))
    return "\n".join(lines).rstrip()


def inject_block_into_prompt(prompt: str, block: str) -> str:
    if not prompt:
        return block
    marker = "\n\n---\n\n"
    return prompt.rstrip() + marker + block + "\n"


def openai_chat_completion(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: float,
) -> tuple[str, dict]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": float(temperature),
        "max_tokens": int(max_output_tokens),
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_CHAT_COMPLETIONS_URL,
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
            with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            choices = payload.get("choices") or []
            if not isinstance(choices, list) or not choices:
                raise RuntimeError("Missing choices in OpenAI response.")
            msg = (choices[0] or {}).get("message") or {}
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Missing message.content in OpenAI response.")
            return content.rstrip() + "\n", payload
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
        except Exception:
            if attempt <= 5:
                time.sleep(min(2 ** (attempt - 1), 30) + random.random())
                continue
            raise


def build_llm_system_message(*, language: str) -> str:
    if language == "en":
        return (
            "You are a prompt refiner. You rewrite system prompts so an agent behaves in a repo-specific, evidence-based way.\n"
            "Rules:\n"
            "- Output ONLY the updated system prompt (markdown). No preamble.\n"
            "- Do not invent repo facts. Only use provided insights.\n"
            "- Prefer concise, actionable rules.\n"
            "- If insights are weak/uncertain, add clarifying-question behavior instead of hard rules.\n"
        )
    return (
        "당신은 시스템 프롬프트 리파이너입니다. 에이전트가 레포 맥락에 맞게, 증거 기반으로 동작하도록 시스템 프롬프트를 재작성합니다.\n"
        "규칙:\n"
        "- 출력은 업데이트된 시스템 프롬프트(마크다운)만. 설명/머리말 금지.\n"
        "- 레포 사실을 꾸며내지 말고 제공된 인사이트만 사용.\n"
        "- 간결하고 실행 가능한 규칙을 우선.\n"
        "- 근거가 약하면 규칙으로 단정하지 말고, 확인 질문/불확실성 처리 규칙을 추가.\n"
    )


def build_llm_user_message(
    *,
    agent_id: str,
    purpose: str,
    current_prompt: str,
    repo_full_name: str,
    injected_block: str,
    language: str,
) -> str:
    if language == "en":
        return (
            f"Agent ID: {agent_id}\n"
            f"Repo: {repo_full_name}\n"
            f"Purpose: {purpose}\n\n"
            "Current system prompt (markdown):\n"
            "-----\n"
            f"{current_prompt.strip()}\n"
            "-----\n\n"
            "Repo insights to incorporate (bounded, evidence-based):\n"
            "-----\n"
            f"{injected_block.strip()}\n"
            "-----\n\n"
            "Task:\n"
            "- Rewrite the system prompt to incorporate the insights.\n"
            "- Include a 'Repo-Specific Context' section.\n"
            "- Preserve the agent's mission/purpose.\n"
        )
    return (
        f"Agent ID: {agent_id}\n"
        f"Repo: {repo_full_name}\n"
        f"Purpose: {purpose}\n\n"
        "현재 시스템 프롬프트(마크다운):\n"
        "-----\n"
        f"{current_prompt.strip()}\n"
        "-----\n\n"
        "반영할 레포 인사이트(증거 기반, bounded):\n"
        "-----\n"
        f"{injected_block.strip()}\n"
        "-----\n\n"
        "요청:\n"
        "- 인사이트를 반영해 시스템 프롬프트를 재작성하세요.\n"
        "- 'Repo-Specific Context' 섹션을 반드시 포함하세요.\n"
        "- 에이전트의 미션/목적은 유지하세요.\n"
    )


def main() -> int:
    args = parse_args()
    if not os.path.isfile(args.agents_summary):
        print(f"AGENTS_SUMMARY.md not found: {args.agents_summary}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.repo_insights):
        print(f"repo_insights.json not found: {args.repo_insights}", file=sys.stderr)
        return 2

    md_text = read_text(args.agents_summary)
    insights = load_json(args.repo_insights)
    repo_full_name = str(insights.get("repo_full_name") or "unknown/unknown")
    cards = insights.get("cards") or []
    if not isinstance(cards, list):
        cards = []

    agents = parse_agents_summary(md_text)
    if not agents:
        print("No agents parsed from AGENTS_SUMMARY.md (expected '## <agent_id>' sections).", file=sys.stderr)
        return 2

    ensure_dir(args.out_dir)

    api_key = os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        print("Missing OPENAI_API_KEY env var (required for prompt updates).", file=sys.stderr)
        return 2

    summary_rows = []
    for a in agents:
        agent_id = str(a.get("agent_id") or "").strip()
        current = str(a.get("current_system_prompt") or "")
        purpose = str(a.get("purpose") or "")

        sel = select_cards_for_agent(cards, purpose=purpose, max_cards=args.max_cards_per_agent)
        block = render_injected_block(sel, repo_full_name=repo_full_name, language=args.language)
        system_msg = build_llm_system_message(language=args.language)
        user_msg = build_llm_user_message(
            agent_id=agent_id,
            purpose=purpose,
            current_prompt=current,
            repo_full_name=repo_full_name,
            injected_block=block,
            language=args.language,
        )
        updated, raw_llm = openai_chat_completion(
            api_key=api_key,
            model=args.model,
            system=system_msg,
            user=user_msg,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
        )

        safe_id = slugify_agent_id(agent_id)
        out_prompt = os.path.join(args.out_dir, f"{safe_id}.system.prompt.md")
        out_changes = os.path.join(args.out_dir, f"{safe_id}.changes.json")

        with open(out_prompt, "w", encoding="utf-8") as f:
            f.write(updated)
            if not updated.endswith("\n"):
                f.write("\n")

        change_payload = {
            "agent_id": agent_id,
            "repo_full_name": repo_full_name,
            "generated_at_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "generation_mode": "openai_chat_completions",
            "llm": {
                "model": args.model,
                "temperature": args.temperature,
                "max_output_tokens": args.max_output_tokens,
                "response_id": str((raw_llm or {}).get("id") or ""),
            },
            "selected_card_ids": [str(c.get("id") or "") for c in sel if isinstance(c, dict) and c.get("id")],
            "evidence_urls": sorted(
                set(
                    ev.get("url")
                    for c in sel
                    for ev in (c.get("evidence") or [])
                    if isinstance(c, dict) and isinstance(c.get("evidence"), list) and isinstance(ev, dict) and isinstance(ev.get("url"), str)
                )
            ),
            "policy": {
                "max_cards_per_agent": args.max_cards_per_agent,
                "evidence_urls_per_card_cap": 3,
                "injection_style": "llm_rewrite",
            },
        }
        with open(out_changes, "w", encoding="utf-8") as f:
            json.dump(change_payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")

        summary_rows.append((agent_id, out_prompt, out_changes, len(sel)))

    print(f"Wrote {len(summary_rows)} agent prompt(s) to: {args.out_dir}")
    for agent_id, p_prompt, p_changes, n_sel in summary_rows:
        print(f"- {agent_id}: cards={n_sel} prompt={p_prompt} changes={p_changes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
