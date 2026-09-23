"""Explicit transfer along existing edges. Does not invent analogs or nodes.

「这和你已有的 X 是同一类取舍」only if a path already exists.
No path: stop. Human may mark related_to.
"""

from __future__ import annotations

from lynote.contracts.models import Claim, LinkCandidate, TransferRef
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.layers import _has_opposition

_LIMIT = 3
_CANDIDATE_LIMIT = 4


def find_transfers(
    anchors: list[Claim],
    store: InMemoryGraphStore,
    *,
    limit: int = _LIMIT,
) -> list[TransferRef]:
    if not anchors:
        return []
    skip = _skip_ids(anchors, store)
    scope = _topic_scope(anchors, store)
    found: list[TransferRef] = []
    seen: set[str] = set()
    for anchor in anchors:
        concepts = _claim_concepts(store, anchor.id)
        reachable = set(concepts)
        for concept_id in concepts:
            reachable.update(_related_concepts(store, concept_id))
        for concept_id in reachable:
            for other_id in _claims_on_concept(store, concept_id):
                if other_id in skip or other_id in seen or other_id not in scope:
                    continue
                other = store.claims.get(other_id)
                if other is None or other.status in {"candidate", "deprecated"}:
                    continue
                if not _has_opposition(store, other):
                    continue
                seen.add(other_id)
                path = [anchor.id]
                own = _claim_concepts(store, anchor.id)
                if concept_id not in own:
                    via = next(iter(own & _related_concepts(store, concept_id)), None)
                    if via:
                        path.append(via)
                path.append(concept_id)
                path.append(other.id)
                found.append(
                    TransferRef(
                        from_id=anchor.id,
                        from_label=anchor.text,
                        to_id=other.id,
                        to_label=other.text,
                        path_ids=path,
                        reason="同一类取舍",
                    )
                )
                if len(found) >= limit:
                    return found
    return found


def suggest_unconnected_tradeoffs(
    anchors: list[Claim],
    store: InMemoryGraphStore,
) -> list[LinkCandidate]:
    """Offer 标成相关 for in-topic tradeoffs with no path. Does not claim they match."""
    if not anchors:
        return []
    reachable = {item.to_id for item in find_transfers(anchors, store)}
    skip = _skip_ids(anchors, store) | reachable
    scope = _topic_scope(anchors, store)
    anchor = anchors[0]
    candidates: list[LinkCandidate] = []
    for claim_id in scope:
        if claim_id in skip or claim_id not in store.claims:
            continue
        other = store.claims[claim_id]
        if other.status in {"candidate", "deprecated"}:
            continue
        if not _has_opposition(store, other):
            continue
        if _claim_concepts(store, claim_id) & _expanded_concepts(store, anchor.id):
            continue
        candidates.append(
            LinkCandidate(
                from_id=anchor.id,
                to_id=other.id,
                from_kind="claim",
                to_kind="claim",
                from_label=anchor.text,
                to_label=other.text,
            )
        )
        if len(candidates) >= _CANDIDATE_LIMIT:
            break
    return candidates


def _skip_ids(anchors: list[Claim], store: InMemoryGraphStore) -> set[str]:
    skip = {claim.id for claim in anchors}
    for claim in anchors:
        skip.update(claim.opposed_claim_ids)
        for rel in store.relations.values():
            if rel.type != "contradicts":
                continue
            if rel.from_id == claim.id:
                skip.add(rel.to_id)
            elif rel.to_id == claim.id:
                skip.add(rel.from_id)
    return skip


def _topic_scope(anchors: list[Claim], store: InMemoryGraphStore) -> set[str]:
    claim_ids = {claim.id for claim in anchors}
    goal_ids: set[str] = set()
    for rel in store.relations.values():
        if rel.type != "about":
            continue
        if rel.from_id in claim_ids and rel.to_id in store.goals:
            goal_ids.add(rel.to_id)
        if rel.to_id in claim_ids and rel.from_id in store.goals:
            goal_ids.add(rel.from_id)
    if not goal_ids:
        for rel in store.relations.values():
            if rel.type != "about":
                continue
            if rel.from_id in claim_ids and rel.to_id in store.concepts:
                for other in store.relations.values():
                    if other.type == "about" and other.to_id == rel.to_id and other.from_id in store.goals:
                        goal_ids.add(other.from_id)
                    if other.type == "about" and other.from_id == rel.to_id and other.to_id in store.goals:
                        goal_ids.add(other.to_id)
    if not goal_ids:
        return set(store.claims)
    scoped: set[str] = set()
    for goal_id in goal_ids:
        scoped.update(node.id for node in store.neighborhood(goal_id).nodes)
    return scoped


def _claim_concepts(store: InMemoryGraphStore, claim_id: str) -> set[str]:
    out: set[str] = set()
    for rel in store.relations.values():
        if rel.type != "about":
            continue
        if rel.from_id == claim_id and rel.to_id in store.concepts:
            out.add(rel.to_id)
        elif rel.to_id == claim_id and rel.from_id in store.concepts:
            out.add(rel.from_id)
    return out


def _related_concepts(store: InMemoryGraphStore, concept_id: str) -> set[str]:
    out: set[str] = set()
    for rel in store.relations.values():
        if rel.type != "related_to":
            continue
        if rel.from_id == concept_id and rel.to_id in store.concepts:
            out.add(rel.to_id)
        elif rel.to_id == concept_id and rel.from_id in store.concepts:
            out.add(rel.from_id)
    return out


def _expanded_concepts(store: InMemoryGraphStore, claim_id: str) -> set[str]:
    own = _claim_concepts(store, claim_id)
    extra: set[str] = set(own)
    for concept_id in own:
        extra.update(_related_concepts(store, concept_id))
    return extra


def _claims_on_concept(store: InMemoryGraphStore, concept_id: str) -> set[str]:
    out: set[str] = set()
    for rel in store.relations.values():
        if rel.type != "about":
            continue
        if rel.to_id == concept_id and rel.from_id in store.claims:
            out.add(rel.from_id)
        elif rel.from_id == concept_id and rel.to_id in store.claims:
            out.add(rel.to_id)
    return out
