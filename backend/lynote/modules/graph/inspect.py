"""Inspect a graph node for the workbench. No LLM. Never invent source_span."""

from __future__ import annotations

from lynote.contracts.models import (
    Claim,
    Evidence,
    EvidenceExcerpt,
    GraphNode,
    NodeDetail,
    Source,
)
from lynote.modules.graph.store import InMemoryGraphStore


def inspect_node(store: InMemoryGraphStore, node_id: str) -> NodeDetail:
    if node_id in store.claims:
        return _claim_detail(store, store.claims[node_id])
    if node_id in store.sources:
        return _source_detail(store, store.sources[node_id])
    if node_id in store.concepts:
        concept = store.concepts[node_id]
        return NodeDetail(
            id=concept.id,
            kind="concept",
            label=concept.name,
            summary=concept.definition,
            definition=concept.definition,
            aliases=list(concept.aliases),
            domain=concept.domain,
            neighbors=_neighbors(store, node_id),
        )
    if node_id in store.goals:
        goal = store.goals[node_id]
        return NodeDetail(
            id=goal.id,
            kind="goal",
            label=goal.title,
            status=goal.status,
            summary=goal.question,
            question=goal.question,
            neighbors=_neighbors(store, node_id),
        )
    if node_id in store.decisions:
        decision = store.decisions[node_id]
        return NodeDetail(
            id=decision.id,
            kind="decision",
            label=decision.question,
            status=decision.status,
            summary=decision.question,
            question=decision.question,
            options=list(decision.options),
            chosen_option_id=decision.chosen_option_id,
            rationale=decision.rationale,
            outcome=decision.outcome,
            neighbors=_neighbors(store, node_id),
        )
    if node_id in store.misconceptions:
        item = store.misconceptions[node_id]
        claim = store.claims.get(item.claim_id)
        return NodeDetail(
            id=item.id,
            kind="misconception",
            label=item.text,
            status=item.status,
            summary=item.text,
            question=claim.text if claim else None,
            claim_id=item.claim_id,
            count=item.count,
            verdict=item.verdict,
            neighbors=_neighbors(store, node_id),
        )
    raise KeyError(node_id)


def excerpt_from_evidence(
    store: InMemoryGraphStore,
    evidence: Evidence,
    *,
    claim_id: str | None = None,
    claim_text: str | None = None,
) -> EvidenceExcerpt:
    source = store.sources.get(evidence.source_id)
    title = source.title if source else evidence.source_id
    body = (source.text or "") if source else ""
    span = evidence.source_span
    quote = evidence.quote
    if source is None:
        return EvidenceExcerpt(
            claim_id=claim_id,
            claim_text=claim_text,
            source_id=evidence.source_id,
            source_title=title,
            quote=quote,
            source_span=span,
            aligned=False,
            note="来源不在图上",
        )
    if not body:
        return EvidenceExcerpt(
            claim_id=claim_id,
            claim_text=claim_text,
            source_id=source.id,
            source_title=title,
            quote=quote,
            source_span=span,
            aligned=False,
            note="来源没有正文，无法高亮",
        )
    if span is None:
        return EvidenceExcerpt(
            claim_id=claim_id,
            claim_text=claim_text,
            source_id=source.id,
            source_title=title,
            quote=quote,
            aligned=False,
            before=body,
            note="没有 source_span，不能高亮，也不会补猜偏移",
        )
    if span.start < 0 or span.end > len(body) or span.start >= span.end:
        return EvidenceExcerpt(
            claim_id=claim_id,
            claim_text=claim_text,
            source_id=source.id,
            source_title=title,
            quote=quote,
            source_span=span,
            aligned=False,
            before=body,
            note="source_span 越界，按原文展示，不改偏移",
        )
    hit = body[span.start : span.end]
    aligned = True
    note = None
    if quote is not None and hit != quote:
        aligned = False
        note = "quote 与 span 切出的原文不一致；高亮仍用已存 span，不重新定位"
    return EvidenceExcerpt(
        claim_id=claim_id,
        claim_text=claim_text,
        source_id=source.id,
        source_title=title,
        quote=quote,
        source_span=span,
        aligned=aligned,
        before=body[: span.start],
        hit=hit,
        after=body[span.end :],
        note=note,
    )


def _claim_detail(store: InMemoryGraphStore, claim: Claim) -> NodeDetail:
    excerpts = [
        excerpt_from_evidence(
            store,
            item,
            claim_id=claim.id,
            claim_text=claim.text,
        )
        for item in claim.evidence
    ]
    return NodeDetail(
        id=claim.id,
        kind="claim",
        label=claim.text,
        status=claim.status,
        summary=claim.text,
        polarity=claim.polarity,
        confidence=claim.confidence,
        opposed_claim_ids=list(claim.opposed_claim_ids),
        excerpts=excerpts,
        neighbors=_neighbors(store, claim.id),
    )


def _source_detail(store: InMemoryGraphStore, source: Source) -> NodeDetail:
    excerpts: list[EvidenceExcerpt] = []
    for claim in store.claims.values():
        for item in claim.evidence:
            if item.source_id != source.id:
                continue
            excerpts.append(
                excerpt_from_evidence(
                    store,
                    item,
                    claim_id=claim.id,
                    claim_text=claim.text,
                )
            )
    return NodeDetail(
        id=source.id,
        kind="source",
        label=source.title,
        summary=source.title,
        uri=source.uri,
        body=source.text,
        excerpts=excerpts,
        neighbors=_neighbors(store, source.id),
    )


def _neighbors(store: InMemoryGraphStore, node_id: str) -> list[GraphNode]:
    nodes: list[GraphNode] = []
    seen: set[str] = set()
    for rel in store.relations.values():
        other = rel.to_id if rel.from_id == node_id else rel.from_id if rel.to_id == node_id else None
        if other is None or other in seen:
            continue
        ref = store.as_node(other)
        if ref is None:
            continue
        seen.add(other)
        nodes.append(ref)
    return nodes
