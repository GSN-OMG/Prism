from __future__ import annotations

from .types import AgentOutput, Issue, IssueAnalysis


def draft_response(issue: Issue, analysis: IssueAnalysis) -> AgentOutput:
    if analysis.missing_info_questions:
        questions = "\n".join(f"- {q}" for q in analysis.missing_info_questions)
        body = (
            "Thanks for the report — to help us reproduce and confirm the fix, could you provide:\n"
            f"{questions}\n"
        )
        return AgentOutput(title=f"Info request for #{issue.number}", body=body)

    body = (
        "Thanks for reaching out. Based on the details provided, here are a few next steps:\n"
        "- Please confirm your environment/version.\n"
        "- Share any logs or error messages.\n"
        "- If possible, provide a minimal reproduction.\n"
    )
    return AgentOutput(title=f"Draft response for #{issue.number}", body=body)

