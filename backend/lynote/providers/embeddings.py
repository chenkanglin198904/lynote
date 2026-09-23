"""Embedding providers. Swap the class later; keep the protocol."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

from lynote.config import settings
from lynote.llm.client import LlmError, apply_caller


class EmbeddingProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Local placeholder so hybrid retrieve works without a vendor key.

    Not for production quality. Replace with OpenAICompatibleEmbedder or another
    provider when EMBEDDING_API_KEY / LLM_API_KEY is set.
    """

    name = "hashing"

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vector(text, self.dim) for text in texts]


class OpenAICompatibleEmbedder:
    """POST /embeddings against any OpenAI-compatible gateway."""

    name = "openai_compatible"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.resolved_embedding_key()
        self.base_url = base_url or settings.resolved_embedding_base_url()
        self.model = model or settings.embedding_model_name
        self.timeout = timeout if timeout is not None else settings.llm_timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.is_available():
            raise LlmError("EMBEDDING_API_KEY / LLM_API_KEY is empty")
        if not texts:
            return []
        url = self.base_url + "/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = apply_caller(
            {"model": self.model, "input": texts},
            settings.resolved_embedding_caller(),
        )
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise LlmError(f"embedding HTTP error: {exc}") from exc
        try:
            rows = sorted(payload["data"], key=lambda item: item["index"])
            return [list(map(float, item["embedding"])) for item in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise LlmError("embedding response missing data[].embedding") from exc


def build_embedder() -> EmbeddingProvider:
    if settings.resolved_embedding_key():
        return OpenAICompatibleEmbedder()
    return HashingEmbedder(dim=min(settings.embedding_dim, 256))


def _hash_vector(text: str, dim: int) -> list[float]:
    compact = re.sub(r"\s+", "", text.lower())
    grams = [compact[i : i + 2] for i in range(max(len(compact) - 1, 0))] or [compact or " "]
    vector = [0.0] * dim
    for gram in grams:
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
