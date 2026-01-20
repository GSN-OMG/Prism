from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.helpers.dotenv import load_dotenv  # noqa: E402

load_dotenv(
    PROJECT_ROOT.parent.parent / ".env",
    PROJECT_ROOT.parent / ".env",
    PROJECT_ROOT / ".env",
)

from devrel.agents.assignment import analyze_issue, recommend_assignee  # noqa: E402
from devrel.agents.docs import detect_doc_gaps, to_doc_gap_output  # noqa: E402
from devrel.agents.promotion import evaluate_promotion  # noqa: E402
from devrel.agents.response import draft_response  # noqa: E402
from devrel.llm.client import LlmClient  # noqa: E402
from devrel.agents.assignment import analyze_issue_llm, recommend_assignee_llm  # noqa: E402
from devrel.agents.response import draft_response_llm  # noqa: E402
from devrel.agents.docs import detect_doc_gaps_llm  # noqa: E402
from devrel.agents.promotion import evaluate_promotion_llm  # noqa: E402
from tests.helpers.github_fixtures import (  # noqa: E402
    contributor_from_profile_json,
    issue_from_github_json,
    load_json,
)


def _print_section(title: str) -> None:
    print()
    print(f"== {title} ==")


def main() -> None:
    issues = [
        issue_from_github_json(load_json("github/issue_bug_oauth.json")),
        issue_from_github_json(load_json("github/issue_question_logging.json")),
        issue_from_github_json(load_json("github/issue_docs_redis.json")),
    ]
    contributors = [
        contributor_from_profile_json(item) for item in load_json("github/contributors.json")
    ]

    use_llm = os.getenv("USE_LLM", "0") in ("1", "true", "TRUE", "yes", "YES")
    llm = LlmClient() if use_llm else None

    _print_section("Issue Analysis + Assignment + Response")
    for issue in issues:
        if llm:
            analysis = analyze_issue_llm(llm, issue)
            assignment = recommend_assignee_llm(
                llm, issue=issue, issue_analysis=analysis, contributors=contributors, limit=3
            )
            response = draft_response_llm(llm, issue=issue, analysis=analysis, references=[])
        else:
            analysis = analyze_issue(issue)
            assignment = recommend_assignee(analysis, contributors, limit=3)
            response = draft_response(issue, analysis)

        print(f"- #{issue.number}: {issue.title}")
        print(f"  issue_type={analysis.issue_type.value}, priority={analysis.priority.value}")
        print(f"  keywords={list(analysis.keywords)}")
        print(f"  assignee={assignment.recommended_assignee} (confidence={assignment.confidence:.2f})")
        print(f"  response_strategy={response.strategy.value}")
        print(f"  response_text:\n{_indent(response.response_text)}")

    _print_section("Doc Gaps")
    if llm:
        gap = detect_doc_gaps_llm(llm, issues)
        print(
            f"- topic={gap.gap_topic}, affected={list(gap.affected_issues)}, path={gap.suggested_doc_path}"
        )
    else:
        for candidate in detect_doc_gaps(issues):
            gap = to_doc_gap_output(candidate)
            print(
                f"- topic={gap.gap_topic}, affected={list(gap.affected_issues)}, path={gap.suggested_doc_path}"
            )

    _print_section("Promotions")
    for c in contributors:
        promo = evaluate_promotion_llm(llm, c) if llm else evaluate_promotion(c)
        print(
            f"- @{c.login}: {promo.current_stage} -> {promo.suggested_stage}, "
            f"candidate={promo.is_candidate}, confidence={promo.confidence:.2f}"
        )

    if os.getenv("RUN_LLM_JUDGE", "0") not in ("1", "true", "TRUE", "yes", "YES"):
        return

    _print_section("LLM Judge (opt-in)")
    from tests.helpers.llm_judge import judge_response_text

    for issue in issues:
        analysis = analyze_issue(issue)
        response = draft_response(issue, analysis)
        result = judge_response_text(issue=issue, analysis=analysis, response_text=response.response_text)
        print(f"- #{issue.number}: passed={result.passed}, score={result.score}")
        if result.feedback:
            print(f"  feedback: {result.feedback}")


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.rstrip().splitlines())


if __name__ == "__main__":
    main()
