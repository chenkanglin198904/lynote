"""Personalized misconceptions hung on the claim they refute. No invented claims."""

from __future__ import annotations

from datetime import datetime, timezone

from lynote.contracts.models import (
    ChatMessage,
    GraphSnapshot,
    Misconception,
    MisconceptionRef,
    ProbeGrade,
    Relation,
)
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.lexical import coverage
from lynote.modules.retrieve.service import _claim_blob

_STREAK_TO_RESOLVE = 2
_RELATED = 0.12
_SEED = 0.08


def record_from_grade(
    store: InMemoryGraphStore,
    grade: ProbeGrade,
    *,
    goal_id: str,
) -> Misconception | None:
    if grade.verdict not in {"gap", "contrary"}:
        return None
    claim = store.claims.get(grade.target_claim_id)
    if claim is None:
        return None
    text = (grade.answer_text or "").strip() or "作答未覆盖已确认主张"
    now = _now()
    existing = _find(store, grade.target_claim_id, goal_id)
    if existing is not None:
        existing.text = text
        existing.count += 1
        existing.correct_streak = 0
        existing.last_seen_at = now
        existing.status = "active"
        existing.verdict = grade.verdict  # type: ignore[assignment]
        saved = store.upsert_misconception(existing)
        _ensure_edges(store, saved)
        return saved
    item = Misconception(
        id=new_id("misc"),
        text=text,
        claim_id=claim.id,
        goal_id=goal_id,
        count=1,
        correct_streak=0,
        last_seen_at=now,
        status="active",
        verdict=grade.verdict,  # type: ignore[arg-type]
    )
    saved = store.upsert_misconception(item)
    _ensure_edges(store, saved)
    return saved


def note_correct(
    store: InMemoryGraphStore,
    claim_id: str,
    *,
    goal_id: str,
) -> Misconception | None:
    existing = _find(store, claim_id, goal_id)
    if existing is None or existing.status != "active":
        return None
    existing.correct_streak += 1
    existing.last_seen_at = _now()
    if existing.correct_streak >= _STREAK_TO_RESOLVE:
        existing.status = "resolved"
    return store.upsert_misconception(existing)


def resolve_misconception(store: InMemoryGraphStore, item_id: str) -> Misconception:
    item = store.misconceptions.get(item_id)
    if item is None:
        raise KeyError(item_id)
    item.status = "resolved"
    item.last_seen_at = _now()
    return store.upsert_misconception(item)


def force_pin_ids(
    store: InMemoryGraphStore,
    query: str,
    *,
    goal_id: str | None,
) -> list[str]:
    pins: list[str] = []
    for item in store.misconceptions.values():
        if item.status != "active":
            continue
        if goal_id and item.goal_id and item.goal_id != goal_id:
            continue
        claim = store.claims.get(item.claim_id)
        if claim is None:
            continue
        blob = f"{item.text} {_claim_blob(claim)}"
        if coverage(query, blob) >= _RELATED:
            pins.append(claim.id)
            pins.append(item.id)
    return pins


def merge_related(
    store: InMemoryGraphStore,
    subgraph: GraphSnapshot,
    query: str,
    *,
    goal_id: str | None,
) -> tuple[GraphSnapshot, list[Misconception]]:
    related = find_related(store, subgraph, query, goal_id=goal_id)
    if not related:
        return subgraph, []
    node_ids = {node.id for node in subgraph.nodes}
    for item in related:
        node_ids.add(item.id)
        node_ids.add(item.claim_id)
        claim = store.claims.get(item.claim_id)
        if claim is None:
            continue
        for evidence in claim.evidence:
            node_ids.add(evidence.source_id)
    return store._snapshot_ids(node_ids), related


def find_related(
    store: InMemoryGraphStore,
    subgraph: GraphSnapshot,
    query: str,
    *,
    goal_id: str | None,
) -> list[Misconception]:
    claim_ids: set[str] = set()
    concept_ids: set[str] = set()
    source_ids: set[str] = set()
    for node in subgraph.nodes:
        if node.kind == "claim" and node.id in store.claims:
            if coverage(query, _claim_blob(store.claims[node.id])) >= _SEED:
                claim_ids.add(node.id)
        elif node.kind == "concept" and node.id in store.concepts:
            concept = store.concepts[node.id]
            in_query = coverage(concept.name, query) >= 0.35 or concept.name in query.replace(" ", "")
            if in_query:
                concept_ids.add(concept.id)
        elif node.kind == "source" and node.id in store.sources:
            source = store.sources[node.id]
            blob = f"{source.title} {source.text or ''}"
            if coverage(query, blob) >= _SEED:
                source_ids.add(source.id)
    for rel in store.relations.values():
        if rel.from_id in claim_ids and rel.to_id in store.claims:
            claim_ids.add(rel.to_id)
        if rel.to_id in claim_ids and rel.from_id in store.claims:
            claim_ids.add(rel.from_id)
        if rel.type == "about":
            if rel.from_id in store.claims and rel.to_id in concept_ids:
                claim_ids.add(rel.from_id)
            if rel.to_id in store.claims and rel.from_id in concept_ids:
                claim_ids.add(rel.to_id)
    for claim in store.claims.values():
        if any(item.source_id in source_ids for item in claim.evidence):
            claim_ids.add(claim.id)
    hits: list[Misconception] = []
    for item in store.misconceptions.values():
        if item.status != "active":
            continue
        if goal_id and item.goal_id and item.goal_id != goal_id:
            continue
        claim = store.claims.get(item.claim_id)
        if claim is None:
            continue
        lexical = coverage(query, f"{item.text} {_claim_blob(claim)}") >= _RELATED
        if item.claim_id in claim_ids or lexical:
            hits.append(item)
    return hits


def as_refs(store: InMemoryGraphStore, items: list[Misconception]) -> list[MisconceptionRef]:
    refs: list[MisconceptionRef] = []
    for item in items:
        claim = store.claims.get(item.claim_id)
        refs.append(
            MisconceptionRef(
                id=item.id,
                text=item.text,
                claim_id=item.claim_id,
                claim_label=claim.text if claim else None,
                count=item.count,
                status=item.status,
                verdict=item.verdict,
            )
        )
    return refs


def attach_refs(message: ChatMessage, refs: list[MisconceptionRef]) -> ChatMessage:
    if not refs:
        return message
    lines = [message.content, "", "【常见误区】"]
    for ref in refs:
        correct = f"图上应按：{ref.claim_label}" if ref.claim_label else "见图上对应主张"
        lines.append(f"- 你上次把「{ref.text}」当成对的（{ref.count} 次）。{correct}")
    updates: dict[str, object] = {"content": "\n".join(lines), "misconceptions": refs}
    if message.probe is not None:
        prompt = message.probe.prompt
        if "误区" not in prompt:
            prompt = "结合你上次在这个点上的误区来答。" + prompt
        updates["probe"] = message.probe.model_copy(update={"prompt": prompt})
    return message.model_copy(update=updates)


def _find(store: InMemoryGraphStore, claim_id: str, goal_id: str) -> Misconception | None:
    for item in store.misconceptions.values():
        if item.claim_id == claim_id and item.goal_id == goal_id:
            return item
    return None


def _ensure_edges(store: InMemoryGraphStore, item: Misconception) -> None:
    existing = {(rel.from_id, rel.to_id, rel.type) for rel in store.relations.values()}
    pairs = [(item.id, item.claim_id, "about")]
    if item.goal_id:
        pairs.append((item.id, item.goal_id, "about"))
    for from_id, to_id, rel_type in pairs:
        if (from_id, to_id, rel_type) in existing:
            continue
        if to_id not in store.claims and to_id not in store.goals:
            continue
        store.upsert_relation(
            Relation(
                id=new_id("rel"),
                from_id=from_id,
                to_id=to_id,
                type=rel_type,  # type: ignore[arg-type]
            )
        )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
