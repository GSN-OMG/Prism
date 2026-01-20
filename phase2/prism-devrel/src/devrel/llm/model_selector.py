from __future__ import annotations

import os
from enum import Enum


class LlmTask(str, Enum):
    ISSUE_TRIAGE = "issue_triage"
    ASSIGNMENT = "assignment"
    RESPONSE = "response"
    DOCS = "docs"
    PROMOTION = "promotion"
    JUDGE = "judge"


DEFAULT_MODELS: dict[LlmTask, str] = {
    LlmTask.ISSUE_TRIAGE: "gpt-4.1-mini",
    LlmTask.ASSIGNMENT: "gpt-4.1",
    LlmTask.RESPONSE: "gpt-5-mini",
    LlmTask.DOCS: "gpt-4.1",
    LlmTask.PROMOTION: "gpt-5",
    LlmTask.JUDGE: "gpt-4.1-mini",
}


def model_for(task: LlmTask) -> str:
    key = f"OPENAI_MODEL_{task.value.upper()}"
    return os.getenv(key, DEFAULT_MODELS[task])

