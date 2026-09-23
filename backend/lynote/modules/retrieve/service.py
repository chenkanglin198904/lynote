"""Hybrid retrieve: lexical + optional vectors, then 1–2 hop graph expansion.

Must return an evidence subgraph only. Never generate prose. If nothing scores
above the threshold and nothing is pinned, return empty — do not pad with random claims.
"""

from __future__ import annotations

from lynote.config import settings
from lynote.contracts.models import Claim, GraphSnapshot, PlayId, PracticeStat, Relation
from lynote.llm.client import LlmError
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.context import play_boost
from lynote.modules.retrieve.lexical import coverage
from lynote.providers.embeddings import EmbeddingProvider, build_embedder
from lynote.providers.vectors import VectorStore, build_vector_store

_EXPAND_TYPES = {"evidenced_by", "contradicts", "about", "supports", "related_to"}
_SECOND_HOP = {"evidenced_by", "contradicts"}
_USE_BOOST = 0.06
_USE_BOOST_CAP = 0.18


class RetrieveService:
    def __init__(
        self,
        embedder: EmbeddingProvider | None = None,
        vectors: VectorStore | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> None:
        self.embedder = embedder if embedder is not None else build_embedder()
        self.vectors = vectors if vectors is not None else build_vector_store()
        self.top_k = top_k if top_k is not None else settings.retrieve_top_k
        self.min_score = min_score if min_score is not None else settings.retrieve_min_score

    def sync(self, store: InMemoryGraphStore) -> None:
        items: list[tuple[str, list[float]]] = []
        texts = [(_claim_blob(claim), claim.id) for claim in store.claims.values()]
        if not texts:
            return
        try:
            vectors = self.embedder.embed([text for text, _cid in texts])
        except LlmError:
            return
        for (_blob, claim_id), vector in zip(texts, vectors, strict=False):
            if vector:
                items.append((claim_id, vector))
        if items:
            self.vectors.upsert(items)

    def retrieve(
        self,
        query: str,
        store: InMemoryGraphStore,
        pinned_node_ids: list[str] | None = None,
        allowed_node_ids: list[str] | None = None,
        own_note_boost: float = 0.0,
        skip_candidates: bool = False,
        practice: dict[str, PracticeStat] | None = None,
        play_id: PlayId | None = None,
    ) -> GraphSnapshot:
        pinned = set(pinned_node_ids or [])
        allowed = set(allowed_node_ids) if allowed_node_ids is not None else None
        if allowed is not None:
            allowed.update(pinned)
        query = query.strip()
        if not query and not pinned:
            return GraphSnapshot(nodes=[], edges=[])

        ranked = (
            self._rank_claims(
                query,
                store,
                allowed,
                own_note_boost=own_note_boost,
                skip_candidates=skip_candidates,
                practice=practice,
                play_id=play_id,
            )
            if query
            else []
        )
        hits = [claim_id for claim_id, score in ranked if score >= self.min_score][: self.top_k]
        seed_ids = set(hits)
        seed_ids.update(cid for cid in pinned if cid in store.claims)
        seed_ids.update(self._claims_for_pinned(store, pinned, allowed))

        if not seed_ids and not pinned:
            return GraphSnapshot(nodes=[], edges=[])

        node_ids = set(seed_ids)
        node_ids.update(pinned)
        node_ids.update(self._expand(store, seed_ids, _EXPAND_TYPES, allowed))
        extra_claims = {nid for nid in node_ids if nid in store.claims} - seed_ids
        if extra_claims:
            node_ids.update(self._expand(store, extra_claims, _SECOND_HOP, allowed))

        for claim_id in list(node_ids):
            claim = store.claims.get(claim_id)
            if claim is None:
                continue
            for evidence in claim.evidence:
                if allowed is None or evidence.source_id in allowed or claim_id in seed_ids:
                    node_ids.add(evidence.source_id)
            for opposed in claim.opposed_claim_ids:
                if allowed is None or opposed in allowed:
                    node_ids.add(opposed)

        edges: list[Relation] = []
        for rel in store.relations.values():
            if rel.from_id in node_ids and rel.to_id in node_ids:
                edges.append(rel)
            elif rel.type in _EXPAND_TYPES and (
                rel.from_id in seed_ids or rel.to_id in seed_ids
            ):
                edges.append(rel)
                node_ids.add(rel.from_id)
                node_ids.add(rel.to_id)

        if allowed is not None:
            node_ids = {nid for nid in node_ids if nid in allowed or nid in pinned}
            for claim_id in list(seed_ids):
                claim = store.claims.get(claim_id)
                if claim is None:
                    continue
                for evidence in claim.evidence:
                    node_ids.add(evidence.source_id)

        snapshot = store.snapshot()
        nodes = [node for node in snapshot.nodes if node.id in node_ids]
        kept = {node.id for node in nodes}
        edges = [rel for rel in edges if rel.from_id in kept and rel.to_id in kept]
        return GraphSnapshot(nodes=nodes, edges=edges)

    def _rank_claims(
        self,
        query: str,
        store: InMemoryGraphStore,
        allowed: set[str] | None,
        own_note_boost: float = 0.0,
        skip_candidates: bool = False,
        practice: dict[str, PracticeStat] | None = None,
        play_id: PlayId | None = None,
    ) -> list[tuple[str, float]]:
        lex: dict[str, float] = {}
        for claim in store.claims.values():
            if allowed is not None and claim.id not in allowed:
                continue
            if claim.status == "deprecated":
                continue
            if skip_candidates and claim.status == "candidate":
                continue
            lex[claim.id] = coverage(query, _claim_blob(claim))
        for concept in store.concepts.values():
            if allowed is not None and concept.id not in allowed:
                continue
            in_query = coverage(concept.name, query) >= 0.35 or concept.name in query.replace(" ", "")
            if not in_query:
                continue
            for rel in store.relations.values():
                if rel.type == "about" and rel.to_id == concept.id and rel.from_id in store.claims:
                    if allowed is not None and rel.from_id not in allowed:
                        continue
                    lex[rel.from_id] = max(lex.get(rel.from_id, 0.0), 0.55)
        for item in store.misconceptions.values():
            if item.status != "active" or item.claim_id not in lex:
                continue
            if allowed is not None and item.claim_id not in allowed:
                continue
            lex[item.claim_id] = min(1.0, lex[item.claim_id] + 0.15 * min(item.count, 3))

        if own_note_boost > 0:
            for claim_id, score in list(lex.items()):
                claim = store.claims.get(claim_id)
                if claim is None:
                    continue
                if _from_own_note(store, claim):
                    lex[claim_id] = min(1.0, score + own_note_boost)

        if practice:
            for claim_id, score in list(lex.items()):
                if score <= 0:
                    continue
                boost = _use_boost(practice, claim_id)
                if boost:
                    lex[claim_id] = min(1.0, score + boost)

        if play_id:
            for claim_id, score in list(lex.items()):
                if score <= 0:
                    continue
                boost = play_boost(store, claim_id, play_id)
                if boost:
                    lex[claim_id] = min(1.0, score + boost)

        vec: dict[str, float] = {}
        try:
            query_vec = self.embedder.embed([query])[0]
            for hit in self.vectors.search(query_vec, self.top_k * 3):
                if hit.id in store.claims and (allowed is None or hit.id in allowed):
                    vec[hit.id] = hit.score
        except (LlmError, IndexError, TypeError):
            vec = {}

        combined: dict[str, float] = {}
        ids = set(lex) | set(vec)
        real_vectors = getattr(self.embedder, "name", "") == "openai_compatible" and bool(vec)
        vector_weight = 0.45 if real_vectors else 0.2
        for claim_id in ids:
            lexical = lex.get(claim_id, 0.0)
            vector = max(0.0, vec.get(claim_id, 0.0))
            if vec:
                combined[claim_id] = (1.0 - vector_weight) * lexical + vector_weight * vector
            else:
                combined[claim_id] = lexical
        return sorted(combined.items(), key=lambda item: item[1], reverse=True)

    def _claims_for_pinned(
        self,
        store: InMemoryGraphStore,
        pinned: set[str],
        allowed: set[str] | None,
    ) -> set[str]:
        hits: set[str] = set()
        for node_id in pinned:
            if node_id in store.claims:
                hits.add(node_id)
                continue
            for rel in store.relations.values():
                if rel.from_id == node_id and rel.to_id in store.claims:
                    if allowed is None or rel.to_id in allowed or node_id in pinned:
                        hits.add(rel.to_id)
                if rel.to_id == node_id and rel.from_id in store.claims:
                    if allowed is None or rel.from_id in allowed or node_id in pinned:
                        hits.add(rel.from_id)
        return hits

    def _expand(
        self,
        store: InMemoryGraphStore,
        seeds: set[str],
        types: set[str],
        allowed: set[str] | None,
    ) -> set[str]:
        extra: set[str] = set()
        for rel in store.relations.values():
            if rel.type not in types:
                continue
            if rel.from_id in seeds:
                if allowed is None or rel.to_id in allowed:
                    extra.add(rel.to_id)
            if rel.to_id in seeds:
                if allowed is None or rel.from_id in allowed:
                    extra.add(rel.from_id)
        return extra


def _claim_blob(claim: Claim) -> str:
    quotes = " ".join(item.quote or "" for item in claim.evidence)
    return f"{claim.text} {quotes}"


def _from_own_note(store: InMemoryGraphStore, claim: Claim) -> bool:
    for item in claim.evidence:
        source = store.sources.get(item.source_id)
        if source is not None and source.kind in {"note", "audio", "video"}:
            return True
    return False


def _use_boost(practice: dict[str, PracticeStat], claim_id: str) -> float:
    count = max((stat.use_count for stat in practice.values() if stat.claim_id == claim_id), default=0)
    if count <= 0:
        return 0.0
    return min(_USE_BOOST_CAP, _USE_BOOST * count)
