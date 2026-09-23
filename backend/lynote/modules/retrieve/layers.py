"""Claim layering: keep-in-head vs look-up-when-needed.

Code adjudicates from graph structure and practice. Does not invent principles.
"""

from __future__ import annotations

from typing import Literal

from lynote.contracts.models import Claim, PracticeStat
from lynote.modules.graph.store import InMemoryGraphStore

ClaimLayer = Literal["keep", "lookup"]

_MASTER_CORRECT = 2


def claim_layer(
    store: InMemoryGraphStore,
    claim: Claim,
    practice: dict[str, PracticeStat] | None = None,
    overrides: dict[str, ClaimLayer] | None = None,
) -> ClaimLayer:
    if claim.status in {"candidate", "deprecated"}:
        return "lookup"
    forced = (overrides or {}).get(claim.id)
    if forced == "lookup":
        return "lookup"
    if forced == "keep" and _has_span(claim):
        return "keep"
    if not _has_span(claim):
        return "lookup"
    if _has_opposition(store, claim):
        return "keep"
    if _well_practiced(practice, claim.id):
        return "keep"
    return "lookup"


def _has_span(claim: Claim) -> bool:
    return any(item.source_span is not None for item in claim.evidence)


def _has_opposition(store: InMemoryGraphStore, claim: Claim) -> bool:
    for other_id in claim.opposed_claim_ids:
        other = store.claims.get(other_id)
        if other is not None and other.status != "deprecated":
            return True
    for rel in store.relations.values():
        if rel.type != "contradicts":
            continue
        other_id = rel.to_id if rel.from_id == claim.id else rel.from_id if rel.to_id == claim.id else None
        if other_id is None:
            continue
        other = store.claims.get(other_id)
        if other is not None and other.status != "deprecated":
            return True
    return False


def _well_practiced(practice: dict[str, PracticeStat] | None, claim_id: str) -> bool:
    if not practice:
        return False
    return any(
        stat.claim_id == claim_id and stat.correct_count >= _MASTER_CORRECT
        for stat in practice.values()
    )
