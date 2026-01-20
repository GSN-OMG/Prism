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
        temperature: float | None = None,
        max_output_tokens: int = 600,
    ) -> dict[str, Any]:
        required = set()
        schema_obj = json_schema.schema or {}
        if isinstance(schema_obj, dict):
            required_list = schema_obj.get("required", [])
            if isinstance(required_list, list):
                required = {str(x) for x in required_list}

        def call_openai(*, text_format: dict[str, object], system_prompt: str) -> dict[str, Any]:
            local_max_tokens = max_output_tokens
            for attempt in range(2):
                kwargs: dict[str, object] = {
                    "model": model_for(task),
                    "input": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user},
                    ],
                    "max_output_tokens": local_max_tokens,
                    "text": {"format": text_format},
                }
                if temperature is not None:
                    kwargs["temperature"] = temperature

                resp = self._client.responses.create(**kwargs)

                status = getattr(resp, "status", None)
                incomplete = getattr(resp, "incomplete_details", None)
                reason = None
                if isinstance(incomplete, dict):
                    reason = incomplete.get("reason")
                elif incomplete is not None:
                    reason = getattr(incomplete, "reason", None)

                if status == "incomplete" and reason == "max_output_tokens" and attempt == 0:
                    local_max_tokens = int(local_max_tokens * 2)
                    continue

                break

            text = getattr(resp, "output_text", "") or ""
            if not text:
                output = getattr(resp, "output", None) or []
                collected: list[str] = []
                for item in output:
                    contents = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
                    for content in contents or []:
                        if isinstance(content, dict):
                            ctype = content.get("type")
                            ctext = content.get("text")
                        else:
                            ctype = getattr(content, "type", None)
                            ctext = getattr(content, "text", None)
                        if ctype == "output_text" and ctext:
                            collected.append(str(ctext))
                text = "\n".join(collected).strip()

            if not text:
                raise ValueError("OpenAI response had no output_text")

            data = json.loads(text)
            if required and isinstance(data, dict):
                missing = required - set(data.keys())
                if missing:
                    raise ValueError(f"JSON missing required keys: {sorted(missing)}")
            return data

        json_schema_format: dict[str, object] = {
            "type": "json_schema",
            "name": json_schema.name,
            "schema": json_schema.schema,
            "strict": json_schema.strict,
        }
        if json_schema.description:
            json_schema_format["description"] = json_schema.description

        try:
            return call_openai(text_format=json_schema_format, system_prompt=system)
        except (json.JSONDecodeError, ValueError):
            # Fallback for models that don't reliably escape newlines in JSON schema mode.
            # Still validates required keys (best-effort) after parsing.
            fallback_system = (
                system
                + "\n\nReturn a single JSON object only. Ensure all strings use valid JSON escaping (e.g. \\n)."
            )
            return call_openai(text_format={"type": "json_object"}, system_prompt=fallback_system)
