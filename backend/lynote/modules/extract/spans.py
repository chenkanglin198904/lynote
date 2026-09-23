"""Map a model quote back onto original text. Invented spans are forbidden."""

from __future__ import annotations

import re

from lynote.contracts.models import SourceSpan


def locate_span(text: str, needle: str) -> SourceSpan | None:
    if not text or not needle:
        return None
    direct = text.find(needle)
    if direct >= 0:
        return SourceSpan(start=direct, end=direct + len(needle))
    stripped = needle.strip()
    if stripped != needle:
        return locate_span(text, stripped)
    parts = [part for part in re.split(r"\s+", stripped) if part]
    if not parts:
        return None
    pattern = r"\s+".join(re.escape(part) for part in parts)
    match = re.search(pattern, text)
    if match:
        return SourceSpan(start=match.start(), end=match.end())
    return None
