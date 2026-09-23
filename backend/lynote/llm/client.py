"""OpenAI-compatible JSON completion. Used by gate/extract. Graph storage never calls this."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from lynote.config import settings
from lynote.llm.parse import JsonParseError, parse_json_object


class LlmError(RuntimeError):
    pass


class Completer(Protocol):
    def __call__(self, system: str, user: str) -> dict[str, Any]: ...


def is_configured() -> bool:
    return bool(settings.llm_api_key.strip())


def apply_caller(body: dict[str, Any], caller: str) -> dict[str, Any]:
    """Some OpenAI-compatible gateways require a billing/audit `caller` field."""
    value = caller.strip()
    if value:
        body["caller"] = value
    return body


def complete_json(system: str, user: str) -> dict[str, Any]:
    content = _chat(system, user)
    if not content:
        raise LlmError("LLM returned empty content")
    try:
        return parse_json_object(content)
    except JsonParseError as exc:
        raise LlmError(str(exc)) from exc


def complete_vision_text(images: list[bytes], hint: str = "") -> str:
    """Transcribe visible text from page images. Must not invent unseen sentences."""
    if not images:
        return ""
    parts: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (hint.strip() or "转录这些页面上的全部可见文字。没有字就输出空。"),
        }
    ]
    for blob in images:
        encoded = _b64_jpeg(blob)
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
            }
        )
    return _chat(
        "你只转录图片上可见的文字。不要总结、不要补全、不要翻译、不要发明句子。没有字就输出空。",
        parts,
    )


def _chat(system: str, user_content: str | list[dict[str, Any]]) -> str:
    if not is_configured():
        raise LlmError("LLM_API_KEY is empty")
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    body = apply_caller(
        {
            "model": settings.llm_model_name,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        },
        settings.llm_caller,
    )
    try:
        with httpx.Client(timeout=settings.llm_timeout) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LlmError(f"LLM HTTP error: {exc}") from exc
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("LLM response missing choices[0].message.content") from exc
    if not isinstance(content, str):
        raise LlmError("LLM returned empty content")
    return content.strip()


def complete_audio_transcript(data: bytes, filename: str = "audio.webm") -> str:
    """Speech-to-text. Must not invent unheard sentences."""
    if not data:
        return ""
    if not is_configured():
        raise LlmError("LLM_API_KEY is empty")
    url = settings.llm_base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    name = filename or "audio.webm"
    files = {"file": (name, data, "application/octet-stream")}
    form = apply_caller({"model": settings.llm_model_name}, settings.llm_caller)
    try:
        with httpx.Client(timeout=max(settings.llm_timeout, 120.0)) as client:
            response = client.post(url, headers=headers, files=files, data=form)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LlmError(f"audio transcription HTTP error: {exc}") from exc
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str):
        raise LlmError("audio transcription missing text")
    return text.strip()


def _b64_jpeg(blob: bytes) -> str:
    import base64

    return base64.b64encode(blob).decode("ascii")
