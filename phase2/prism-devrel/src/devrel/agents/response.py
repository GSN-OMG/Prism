from __future__ import annotations

from .types import Issue, IssueAnalysisOutput, ResponseOutput, ResponseStrategy


def draft_response(issue: Issue, analysis: IssueAnalysisOutput) -> ResponseOutput:
    if analysis.needs_more_info:
        body = (
            "Thanks for the report — to help us reproduce and confirm the fix, could you provide:\n"
            "- Steps to reproduce\n"
            "- Expected vs actual behavior\n"
            "- Environment/version\n"
            "- Relevant logs/stack traces\n"
        )
        return ResponseOutput(
            strategy=ResponseStrategy.REQUEST_INFO,
            response_text=body,
            confidence=0.6,
            references=(),
            follow_up_needed=True,
        )

    body = (
        "Thanks for reaching out. Here are a few next steps to unblock:\n"
        "- Confirm your environment/version\n"
        "- Share logs or errors\n"
        "- Provide a minimal reproduction if possible\n"
    )
    return ResponseOutput(
        strategy=analysis.suggested_action,
        response_text=body,
        confidence=0.5,
        references=(),
        follow_up_needed=False,
    )
