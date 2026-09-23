"""Packing list: keep-in-head vs look-up-when-needed, per existing claim ids.

Code splits from graph structure, practice, and human overrides. Does not invent claims.
"""

from __future__ import annotations

from lynote.contracts.models import PackItem, PracticeStat
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.layers import (
    ClaimLayer,
    _has_opposition,
    _has_span,
    _well_practiced,
    claim_layer,
)


def pack_claims(
    store: InMemoryGraphStore,
    claim_ids: list[str],
    practice: dict[str, PracticeStat] | None = None,
    overrides: dict[str, str] | None = None,
) -> tuple[list[PackItem], list[PackItem]]:
    keep: list[PackItem] = []
    lookup: list[PackItem] = []
    seen: set[str] = set()
    for claim_id in claim_ids:
        if claim_id in seen:
            continue
        seen.add(claim_id)
        claim = store.claims.get(claim_id)
        if claim is None or claim.status == "deprecated":
            continue
        layer = claim_layer(store, claim, practice, overrides=overrides)
        source_id = claim.evidence[0].source_id if claim.evidence else None
        item = PackItem(
            id=claim.id,
            label=claim.text,
            layer=layer,
            reason=_reason(store, claim, layer, practice, overrides),
            overridden=claim.id in (overrides or {}),
            source_id=source_id,
        )
        if layer == "keep":
            keep.append(item)
        else:
            lookup.append(item)
    return keep, lookup


def attach_pack(proposal, store, practice=None, overrides=None):
    keep, lookup = pack_claims(store, list(proposal.claim_ids), practice, overrides)
    return proposal.model_copy(update={"pack_keep": keep, "pack_lookup": lookup})


def set_layer_override(
    store: InMemoryGraphStore,
    overrides: dict[str, str],
    claim_id: str,
    layer: str | None,
) -> dict[str, str]:
    claim = store.claims.get(claim_id)
    if claim is None:
        raise KeyError(claim_id)
    next_map = dict(overrides)
    if layer is None:
        next_map.pop(claim_id, None)
        return next_map
    if layer == "keep":
        if claim.status in {"candidate", "deprecated"}:
            raise ValueError("未确认或过时的主张不能标成该内化")
        if not _has_span(claim):
            raise ValueError("没有原文定位，不能标成该内化")
    elif layer != "lookup":
        raise ValueError("只能标成该内化或可外置")
    next_map[claim_id] = layer
    return next_map


def _reason(
    store: InMemoryGraphStore,
    claim,
    layer: ClaimLayer,
    practice: dict[str, PracticeStat] | None,
    overrides: dict[str, str] | None,
) -> str:
    forced = (overrides or {}).get(claim.id)
    if forced == "keep":
        return "你标成该内化"
    if forced == "lookup":
        return "你标成可外置"
    if layer == "keep":
        if _has_opposition(store, claim):
            return "有对立，建议内化"
        if _well_practiced(practice, claim.id):
            return "练过，建议内化"
        return "建议内化"
    if any(item.quote or item.source_span for item in claim.evidence):
        return "有出处，需要时再查"
    return "还没有对立或练习，先外置"
