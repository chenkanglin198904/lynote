"""Lexical scoring for CJK and latin. No vendor dependency."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9_]{2,}", re.I)


def tokens(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", text.lower())
    grams = {compact[i : i + 2] for i in range(max(len(compact) - 1, 0))}
    words = {match.group(0).lower() for match in _WORD.finditer(text)}
    return {item for item in grams | words if item}


def coverage(query: str, document: str) -> float:
    query_tokens = tokens(query)
    if not query_tokens:
        return 0.0
    document_tokens = tokens(document)
    if not document_tokens:
        return 0.0
    hit = len(query_tokens & document_tokens)
    denom = min(max(len(query_tokens), 1), 12)
    return hit / denom
