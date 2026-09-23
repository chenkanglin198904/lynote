"""Cross-topic hits. Listed separately until the human asks to expand."""

from __future__ import annotations

from lynote.contracts.models import CrossTopicHit
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.lexical import coverage
from lynote.modules.retrieve.service import _claim_blob


def find_cross_topic(
    store: InMemoryGraphStore,
    query: str,
    excluded_ids: set[str],
    *,
    limit: int = 4,
) -> list[CrossTopicHit]:
    query = query.strip()
    if not query:
        return []
    ranked: list[tuple[float, CrossTopicHit]] = []
    for claim in store.claims.values():
        if claim.id in excluded_ids or claim.status in {"deprecated", "candidate"}:
            continue
        score = coverage(query, _claim_blob(claim))
        if score < 0.2:
            continue
        goal_id, goal_title = _goal_for(store, claim.id)
        if not goal_id:
            continue
        ranked.append(
            (
                score,
                CrossTopicHit(
                    goal_id=goal_id,
                    goal_title=goal_title,
                    claim_id=claim.id,
                    label=claim.text,
                ),
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    seen: set[str] = set()
    hits: list[CrossTopicHit] = []
    for _score, hit in ranked:
        if hit.claim_id in seen:
            continue
        seen.add(hit.claim_id)
        hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


def _goal_for(store: InMemoryGraphStore, node_id: str) -> tuple[str, str]:
    for rel in store.relations.values():
        if rel.type not in {"about", "belongs_to"}:
            continue
        if rel.from_id == node_id and rel.to_id in store.goals:
            goal = store.goals[rel.to_id]
            return goal.id, goal.title
        if rel.to_id == node_id and rel.from_id in store.goals:
            goal = store.goals[rel.from_id]
            return goal.id, goal.title
    return "", ""
