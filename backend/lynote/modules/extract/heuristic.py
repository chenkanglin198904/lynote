"""Rule fallback extractor. Writes claims with locatable source_span only."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lynote.contracts.models import (
    Claim,
    ClaimPolarity,
    Evidence,
    Relation,
    Source,
    SourceSpan,
)
from lynote.modules.extract.spans import locate_span
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore

if TYPE_CHECKING:
    from lynote.modules.extract.service import Extraction


def extract_heuristic(source: Source, store: InMemoryGraphStore) -> Extraction:
    from lynote.modules.extract.service import Extraction

    text = source.text or source.title
    claim_ids: list[str] = []
    if source.kind in {"note", "audio", "video"}:
        claim_ids.extend(_scratch_claim(source, store, text))
    for sentence in _sentences(text):
        if source.kind in {"note", "audio", "video"} and sentence.strip() == text.strip():
            continue
        if not _looks_like_claim(sentence):
            continue
        span = locate_span(text, sentence)
        if span is None:
            continue
        claim_ids.append(
            upsert_claim(store, source, sentence.strip("。；; "), span, sentence.strip())
        )
    return Extraction(claim_ids=claim_ids, proposed_names=[])


def upsert_claim(
    store: InMemoryGraphStore,
    source: Source,
    text: str,
    span: SourceSpan,
    quote: str,
    polarity: ClaimPolarity = "asserts",
    confidence: float = 0.45,
) -> str:
    claim = Claim(
        id=new_id("claim"),
        text=text,
        polarity=polarity,
        confidence=max(0.0, min(confidence, 1.0)),
        status="candidate",
        evidence=[
            Evidence(
                source_id=source.id,
                quote=quote,
                source_span=span,
            )
        ],
    )
    store.upsert_claim(claim)
    store.upsert_relation(
        Relation(
            id=new_id("rel"),
            from_id=claim.id,
            to_id=source.id,
            type="evidenced_by",
            source_id=source.id,
        )
    )
    return claim.id


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？\n])", text)
    return [part.strip() for part in parts if part.strip()]


def _looks_like_claim(sentence: str) -> bool:
    markers = ("必须", "应该", "不要", "优于", "会变成", "不是", "需要", "禁止")
    return any(marker in sentence for marker in markers) and len(sentence) >= 12


def _scratch_claim(source: Source, store: InMemoryGraphStore, text: str) -> list[str]:
    body = text.strip()
    if len(body) < 8:
        return []
    span = locate_span(text, body) or locate_span(text, body[: min(len(body), 80)])
    if span is None:
        return []
    quote = text[span.start : span.end]
    claim_text = body.strip("。；; \n")
    if len(claim_text) < 8:
        return []
    existing = {claim.text for claim in store.claims.values()}
    if claim_text in existing:
        return []
    return [
        upsert_claim(
            store,
            source,
            claim_text[:240],
            span,
            quote,
            confidence=0.7 if source.kind == "note" else 0.55,
        )
    ]
