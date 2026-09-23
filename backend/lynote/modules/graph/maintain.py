"""Graph hygiene: merge concepts, deprecate stale claims. Does not call an LLM."""

from __future__ import annotations

from lynote.contracts.models import Concept, Relation
from lynote.modules.graph.store import InMemoryGraphStore


def merge_concepts(store: InMemoryGraphStore, keep_id: str, drop_id: str) -> Concept:
    if keep_id == drop_id:
        raise ValueError("不能把概念合并到自己")
    keep = store.concepts.get(keep_id)
    drop = store.concepts.get(drop_id)
    if keep is None:
        raise KeyError(keep_id)
    if drop is None:
        raise KeyError(drop_id)
    aliases = list(keep.aliases)
    if drop.name not in aliases and drop.name != keep.name:
        aliases.append(drop.name)
    for alias in drop.aliases:
        if alias not in aliases and alias != keep.name:
            aliases.append(alias)
    keep.aliases = aliases
    if not keep.definition and drop.definition:
        keep.definition = drop.definition
    store.upsert_concept(keep)
    seen = {(rel.from_id, rel.to_id, rel.type) for rel in store.relations.values()}
    for rel in list(store.relations.values()):
        from_id = keep_id if rel.from_id == drop_id else rel.from_id
        to_id = keep_id if rel.to_id == drop_id else rel.to_id
        if from_id == rel.from_id and to_id == rel.to_id:
            continue
        store.remove_relation(rel.id)
        key = (from_id, to_id, rel.type)
        if from_id == to_id or key in seen:
            continue
        moved = Relation(
            id=rel.id,
            from_id=from_id,
            to_id=to_id,
            type=rel.type,
            weight=rel.weight,
            source_id=rel.source_id,
        )
        store.upsert_relation(moved)
        seen.add(key)
    store.remove_concept(drop_id)
    return keep


def deprecate_claim(store: InMemoryGraphStore, claim_id: str):
    claim = store.claims.get(claim_id)
    if claim is None:
        raise KeyError(claim_id)
    claim.status = "deprecated"
    return store.upsert_claim(claim)
