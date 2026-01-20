from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .model_selector import LlmTask, model_for


@dataclass(frozen=True, slots=True)
class JsonSchema:
    name: str
    schema: dict[str, object]
    strict: bool = True
    description: str | None = None


class LlmClient:
    def __init__(self, *, api_key: str | None = None) -> None:
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=api_key)

    def generate_json(
        self,
        *,
        task: LlmTask,
        system: str,
        user: str,
        json_schema: JsonSchema,
        temperature: float = 0.2,
        max_output_tokens: int = 600,
    ) -> dict[str, Any]:
        text_format: dict[str, object] = {
            "type": "json_schema",
            "name": json_schema.name,
            "schema": json_schema.schema,
            "strict": json_schema.strict,
        }
        if json_schema.description:
            text_format["description"] = json_schema.description

        resp = self._client.responses.create(
            model=model_for(task),
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            text={"format": text_format},
        )
        return json.loads(resp.output_text)

