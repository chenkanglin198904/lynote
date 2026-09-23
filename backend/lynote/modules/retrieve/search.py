"""Topic-scoped knowledge search. Returns ranked hits or unknown. Never invents nodes."""

from __future__ import annotations

import re

from lynote.contracts.models import KnowledgeHit, KnowledgeSearchResponse, PlayId, PracticeStat
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.context import play_boost
from lynote.modules.retrieve.layers import claim_layer
from lynote.modules.retrieve.lexical import coverage

_MIN_SCORE = 0.12
_LIMIT = 8


def search_knowledge(
    query: str,
    store: InMemoryGraphStore,
    *,
    allowed_ids: list[str] | None = None,
    goal_id: str | None = None,
    practice: dict[str, PracticeStat] | None = None,
    overrides: dict[str, str] | None = None,
    play_id: PlayId | None = None,
) -> KnowledgeSearchResponse:
    needle = query.strip()
    if not needle:
        return KnowledgeSearchResponse(query="", goal_id=goal_id, unknown=False)

    allowed = set(allowed_ids) if allowed_ids is not None else None

    concepts: list[KnowledgeHit] = []
    for concept in store.concepts.values():
        if allowed is not None and concept.id not in allowed:
            continue
        blob = " ".join([concept.name, " ".join(concept.aliases), concept.definition or ""])
        score = _score(needle, blob, concept.name)
        if score < _MIN_SCORE:
            continue
        concepts.append(
            KnowledgeHit(
                id=concept.id,
                kind="concept",
                label=concept.name,
                snippet=concept.definition,
                score=score,
                path_ids=_path_ids(store, concept.id, goal_id),
            )
        )

    claims: list[KnowledgeHit] = []
    for claim in store.claims.values():
        if allowed is not None and claim.id not in allowed:
            continue
        quotes = " ".join(item.quote or "" for item in claim.evidence)
        blob = f"{claim.text} {quotes}"
        score = _score(needle, blob, claim.text)
        if score < _MIN_SCORE:
            continue
        if play_id:
            score = min(1.0, score + play_boost(store, claim.id, play_id))
        layer = claim_layer(store, claim, practice, overrides=overrides)
        claims.append(
            KnowledgeHit(
                id=claim.id,
                kind="claim",
                label=claim.text,
                snippet=(claim.evidence[0].quote if claim.evidence else None),
                status=claim.status,
                score=score,
                path_ids=_path_ids(store, claim.id, goal_id),
                layer=layer,
            )
        )

    sources: list[KnowledgeHit] = []
    for source in store.sources.values():
        if allowed is not None and source.id not in allowed:
            continue
        blob = f"{source.title} {source.text or ''}"
        score = _score(needle, blob, source.title)
        if score < _MIN_SCORE:
            continue
        sources.append(
            KnowledgeHit(
                id=source.id,
                kind="source",
                label=source.title,
                snippet=_clip(source.text or "", 80),
                status=source.kind,
                score=score,
                path_ids=_path_ids(store, source.id, goal_id),
            )
        )

    concepts = _top(concepts)
    claims = _top_layered(claims)
    sources = _top(sources)
    unknown = not (concepts or claims or sources)
    return KnowledgeSearchResponse(
        query=needle,
        goal_id=goal_id,
        concepts=concepts,
        claims=claims,
        sources=sources,
        unknown=unknown,
    )


def _score(query: str, blob: str, title: str = "") -> float:
    lex = coverage(query, blob)
    compact_q = re.sub(r"\s+", "", query.lower())
    compact_title = re.sub(r"\s+", "", title.lower())
    compact_blob = re.sub(r"\s+", "", blob.lower())
    if compact_q and compact_q in compact_title:
        return max(lex, 0.85)
    if compact_q and compact_q in compact_blob:
        return max(lex, 0.55)
    return lex


def _top(hits: list[KnowledgeHit], limit: int = _LIMIT) -> list[KnowledgeHit]:
    return sorted(hits, key=lambda item: item.score, reverse=True)[:limit]


def _top_layered(hits: list[KnowledgeHit], limit: int = _LIMIT) -> list[KnowledgeHit]:
    ordered = sorted(
        hits,
        key=lambda item: (0 if item.layer == "keep" else 1, -item.score),
    )
    return ordered[:limit]


def _clip(text: str, size: int) -> str | None:
    compact = text.strip()
    if not compact:
        return None
    if len(compact) <= size:
        return compact
    return compact[:size] + "…"


def _path_ids(store: InMemoryGraphStore, node_id: str, goal_id: str | None) -> list[str]:
    if not goal_id or node_id == goal_id:
        return [node_id]
    adjacent: dict[str, set[str]] = {}
    for rel in store.relations.values():
        adjacent.setdefault(rel.from_id, set()).add(rel.to_id)
        adjacent.setdefault(rel.to_id, set()).add(rel.from_id)
    parent: dict[str, str | None] = {goal_id: None}
    queue = [goal_id]
    while queue:
        current = queue.pop(0)
        if current == node_id:
            break
        for neighbor in adjacent.get(current, ()):
            if neighbor in parent:
                continue
            parent[neighbor] = current
            queue.append(neighbor)
    if node_id not in parent:
        return [node_id]
    trail = [node_id]
    while trail[-1] != goal_id:
        prev = parent.get(trail[-1])
        if prev is None:
            break
        trail.append(prev)
    trail.reverse()
    return trail
