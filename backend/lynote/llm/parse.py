"""JSON helpers for LLM responses. Models often wrap objects in markdown fences."""

from __future__ import annotations

import json
import re
from typing import Any


class JsonParseError(ValueError):
    pass


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise JsonParseError("LLM response is not a JSON object") from None
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise JsonParseError("LLM response is not a JSON object") from exc
    if not isinstance(payload, dict):
        raise JsonParseError("LLM response JSON must be an object")
    return payload
