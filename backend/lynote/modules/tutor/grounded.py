"""Compose a grounded answer from a retrieve subgraph.

Code adjudicates ids. The model is not asked to invent claims.
Sections: 直答 / 需要时再查 / 依据 / 联想 / 边界.
Keep-in-head claims go to 直答. Details stay in lookup. Empty keep does not invent a principle.
"""

from __future__ import annotations

from lynote.contracts.models import (
    ChatMessage,
    Claim,
    GroundedAnswer,
    GroundedRef,
    GraphSnapshot,
    LinkCandidate,
    PracticeStat,
)
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.layers import claim_layer
from lynote.modules.retrieve.lexical import coverage
from lynote.modules.retrieve.service import _claim_blob
from lynote.modules.tutor.probe import attach_probe
from lynote.modules.tutor.transfer import find_transfers, suggest_unconnected_tradeoffs

_KEEP_LIMIT = 2
_LOOKUP_LIMIT = 4
_RELATED_LIMIT = 6
_CANDIDATE_LIMIT = 4
_MIN_DIRECT = 0.08
_UNKNOWN = "召回未命中任何 Claim"
_NO_KEEP = "匹配到的是需要时再查的细节，还没有带对立或经练习的上层主张，不能编一条原理。"
_LINKABLE = {"claim", "concept"}
_LINK_TYPES = {"about", "related_to", "contradicts", "supports"}


def compose_grounded_answer(
    question: str,
    subgraph: GraphSnapshot,
    store: InMemoryGraphStore,
    pinned_node_ids: list[str] | None = None,
    practice: dict[str, PracticeStat] | None = None,
    overrides: dict[str, str] | None = None,
) -> ChatMessage:
    allowed = {node.id for node in subgraph.nodes}
    pinned = set(pinned_node_ids or [])
    claims = [
        store.claims[node.id]
        for node in subgraph.nodes
        if node.kind == "claim" and node.id in store.claims and store.claims[node.id].status != "deprecated"
    ]
    if not claims:
        return _unknown_message()

    ranked = sorted(
        claims,
        key=lambda claim: (
            coverage(question, _claim_blob(claim)),
            1 if claim.status == "confirmed" else 0,
            claim.confidence,
        ),
        reverse=True,
    )
    matched: list[Claim] = []
    for claim in ranked:
        if claim.status == "candidate":
            continue
        score = coverage(question, _claim_blob(claim))
        pinned_hit = claim.id in pinned or bool(
            {claim.id, *(item.source_id for item in claim.evidence)} & pinned
        )
        if score >= _MIN_DIRECT or pinned_hit:
            matched.append(claim)
    if not matched:
        return _unknown_message()

    keep: list[Claim] = []
    lookup: list[Claim] = []
    for claim in matched:
        pinned_hit = claim.id in pinned or bool(
            {claim.id, *(item.source_id for item in claim.evidence)} & pinned
        )
        layer = claim_layer(store, claim, practice, overrides=overrides)
        if pinned_hit or layer == "keep":
            keep.append(claim)
        else:
            lookup.append(claim)
    direct = keep[:_KEEP_LIMIT]
    lookup = keep[_KEEP_LIMIT:] + lookup
    lookup = lookup[:_LOOKUP_LIMIT]
    if not direct and not lookup:
        return _unknown_message()

    direct_ids = {claim.id for claim in direct}
    lookup_ids = {claim.id for claim in lookup}
    evidence_refs = [_evidence_ref(claim, allowed) for claim in [*direct, *lookup]]
    evidence_refs = [item for item in evidence_refs if item is not None]
    related_refs = _related(direct or lookup[:1], subgraph, store, allowed, direct_ids | lookup_ids)
    anchors = direct or lookup[:1]
    transfers = find_transfers(anchors, store)

    conflicts = [
        pair
        for pair in store.conflicts()
        if pair[0].id in allowed and pair[1].id in allowed
    ]
    unknowns: list[str] = []
    unlinked = not related_refs and not transfers
    if conflicts:
        unknowns.append("子图内存在显式冲突，不能只听一侧")
    if not direct and lookup:
        unknowns.append(_NO_KEEP)
    if unlinked:
        candidates = suggest_link_candidates(anchors, store)
    elif not transfers:
        candidates = suggest_unconnected_tradeoffs(anchors, store)
    else:
        candidates = []

    grounded = GroundedAnswer(
        direct=[_claim_ref(claim, "direct", store, practice, overrides) for claim in direct],
        lookup=[_claim_ref(claim, "lookup", store, practice, overrides) for claim in lookup],
        evidence=evidence_refs,
        related=related_refs,
        unknowns=unknowns,
        unlinked=unlinked,
        link_candidates=candidates,
        transfers=transfers,
    )
    grounded = _adjudicate(grounded, allowed)
    answer = ChatMessage(
        id=new_id("msg"),
        role="assistant",
        content=_render(question, grounded),
        claim_ids=_unique(
            [
                ref.id
                for ref in grounded.direct + grounded.lookup + grounded.evidence + grounded.related
                if ref.kind == "claim"
            ]
            + [item.to_id for item in grounded.transfers]
        ),
        unknowns=grounded.unknowns,
        grounded=grounded,
    )
    return attach_probe(answer, store)


def _unknown_message() -> ChatMessage:
    grounded = GroundedAnswer(
        direct=[],
        lookup=[],
        evidence=[],
        related=[],
        unknowns=[_UNKNOWN],
        unlinked=False,
        link_candidates=[],
        transfers=[],
    )
    return ChatMessage(
        id=new_id("msg"),
        role="assistant",
        content=_render("", grounded),
        unknowns=[_UNKNOWN],
        grounded=grounded,
    )


def _claim_ref(
    claim: Claim,
    relation: str,
    store: InMemoryGraphStore | None = None,
    practice: dict[str, PracticeStat] | None = None,
    overrides: dict[str, str] | None = None,
) -> GroundedRef:
    quote = claim.evidence[0].quote if claim.evidence else None
    source_id = claim.evidence[0].source_id if claim.evidence else None
    layer = claim_layer(store, claim, practice, overrides=overrides) if store is not None else None
    return GroundedRef(
        id=claim.id,
        kind="claim",
        label=claim.text,
        status=claim.status,
        quote=quote,
        source_id=source_id,
        relation=relation,
        layer=layer,
    )


def _evidence_ref(claim: Claim, allowed: set[str]) -> GroundedRef | None:
    for item in claim.evidence:
        if item.source_id not in allowed and claim.id not in allowed:
            continue
        return GroundedRef(
            id=claim.id,
            kind="claim",
            label=claim.text,
            status=claim.status,
            quote=item.quote,
            source_id=item.source_id,
            relation="evidenced_by",
        )
    return None


def _related(
    direct: list[Claim],
    subgraph: GraphSnapshot,
    store: InMemoryGraphStore,
    allowed: set[str],
    direct_ids: set[str],
) -> list[GroundedRef]:
    refs: list[GroundedRef] = []
    seen = set(direct_ids)

    concept_ids = {
        node.id
        for node in subgraph.nodes
        if node.kind == "concept" and node.id in allowed
    }
    about: dict[str, set[str]] = {}
    for rel in store.relations.values():
        if rel.type != "about":
            continue
        if rel.from_id in store.claims and rel.to_id in store.concepts:
            about.setdefault(rel.from_id, set()).add(rel.to_id)
        if rel.to_id in store.claims and rel.from_id in store.concepts:
            about.setdefault(rel.to_id, set()).add(rel.from_id)

    for claim in direct:
        for opposed_id in claim.opposed_claim_ids:
            if opposed_id in seen or opposed_id not in allowed or opposed_id not in store.claims:
                continue
            opposed = store.claims[opposed_id]
            seen.add(opposed_id)
            refs.append(_claim_ref(opposed, "contradicts"))
        for rel in store.relations.values():
            if rel.type != "contradicts":
                continue
            other = None
            if rel.from_id == claim.id:
                other = store.claims.get(rel.to_id)
            elif rel.to_id == claim.id:
                other = store.claims.get(rel.from_id)
            if other is None or other.id in seen or other.id not in allowed:
                continue
            seen.add(other.id)
            refs.append(_claim_ref(other, "contradicts"))

    seed_concepts = set()
    for claim in direct:
        seed_concepts.update(about.get(claim.id, ()))
        seed_concepts.update(cid for cid in concept_ids if cid in about.get(claim.id, ()))

    for rel in subgraph.edges:
        if rel.type not in {"about", "related_to"}:
            continue
        if rel.from_id in direct_ids and rel.to_id in store.concepts and rel.to_id in allowed:
            seed_concepts.add(rel.to_id)
        if rel.to_id in direct_ids and rel.from_id in store.concepts and rel.from_id in allowed:
            seed_concepts.add(rel.from_id)

    for concept_id in seed_concepts:
        concept = store.concepts.get(concept_id)
        if concept is None or concept_id in seen or concept_id not in allowed:
            continue
        seen.add(concept_id)
        refs.append(
            GroundedRef(
                id=concept.id,
                kind="concept",
                label=concept.name,
                relation="about",
            )
        )
        for other_id, concepts in about.items():
            if concept_id not in concepts or other_id in seen or other_id not in allowed:
                continue
            other = store.claims.get(other_id)
            if other is None or other.status == "deprecated":
                continue
            seen.add(other_id)
            refs.append(_claim_ref(other, "about"))

    for rel in subgraph.edges:
        if rel.type != "related_to":
            continue
        for node_id in (rel.from_id, rel.to_id):
            if node_id in seen or node_id not in allowed:
                continue
            concept = store.concepts.get(node_id)
            if concept is None:
                continue
            if not (rel.from_id in seed_concepts or rel.to_id in seed_concepts or rel.from_id in direct_ids or rel.to_id in direct_ids):
                continue
            seen.add(node_id)
            refs.append(
                GroundedRef(
                    id=concept.id,
                    kind="concept",
                    label=concept.name,
                    relation="related_to",
                )
            )

    return refs[:_RELATED_LIMIT]


def _adjudicate(answer: GroundedAnswer, allowed: set[str]) -> GroundedAnswer:
    def keep(refs: list[GroundedRef]) -> list[GroundedRef]:
        return [ref for ref in refs if ref.id in allowed]

    return GroundedAnswer(
        direct=keep(answer.direct),
        lookup=keep(answer.lookup),
        evidence=keep(answer.evidence),
        related=keep(answer.related),
        unknowns=list(answer.unknowns),
        unlinked=answer.unlinked,
        link_candidates=list(answer.link_candidates),
        transfers=list(answer.transfers),
    )


def suggest_link_candidates(direct: list[Claim], store: InMemoryGraphStore) -> list[LinkCandidate]:
    if not direct:
        return []
    direct_ids = {claim.id for claim in direct}
    blocked = _linked_ids(direct_ids, store)
    mates = _topic_mates(direct, store)
    concepts: list[str] = []
    claims: list[str] = []
    for node_id in mates:
        if node_id in blocked or node_id in direct_ids:
            continue
        if node_id in store.concepts:
            concepts.append(node_id)
        elif node_id in store.claims and store.claims[node_id].status != "deprecated":
            claims.append(node_id)
    anchor = direct[0]
    candidates: list[LinkCandidate] = []
    for target_id in concepts + claims:
        node = store.as_node(target_id)
        if node is None or node.kind not in _LINKABLE:
            continue
        candidates.append(
            LinkCandidate(
                from_id=anchor.id,
                to_id=target_id,
                from_kind="claim",
                to_kind=node.kind,
                from_label=anchor.text,
                to_label=node.label,
            )
        )
        if len(candidates) >= _CANDIDATE_LIMIT:
            break
    return candidates


def _linked_ids(direct_ids: set[str], store: InMemoryGraphStore) -> set[str]:
    linked = set(direct_ids)
    for rel in store.relations.values():
        if rel.type not in _LINK_TYPES:
            continue
        if rel.from_id in direct_ids:
            linked.add(rel.to_id)
        if rel.to_id in direct_ids:
            linked.add(rel.from_id)
    return linked


def _topic_mates(direct: list[Claim], store: InMemoryGraphStore) -> set[str]:
    goal_ids: set[str] = set()
    claim_ids = {claim.id for claim in direct}
    for rel in store.relations.values():
        if rel.type != "about":
            continue
        if rel.from_id in claim_ids and rel.to_id in store.goals:
            goal_ids.add(rel.to_id)
        if rel.to_id in claim_ids and rel.from_id in store.goals:
            goal_ids.add(rel.from_id)
    if not goal_ids:
        return set(store.concepts) | set(store.claims)
    mates: set[str] = set()
    for goal_id in goal_ids:
        mates.update(node.id for node in store.neighborhood(goal_id).nodes)
    return mates


def _render(question: str, answer: GroundedAnswer) -> str:
    lines: list[str] = []
    if question.strip() and (answer.direct or answer.lookup):
        lines.append(f"针对「{question.strip()}」")
        lines.append("")
    lines.append("【直答】")
    if answer.direct:
        for ref in answer.direct:
            status = f"（{ref.status}）" if ref.status else ""
            tag = "〔上层〕" if ref.layer == "keep" else ("〔细节〕" if ref.layer == "lookup" else "")
            lines.append(f"- {tag}{ref.label}{status}")
    else:
        lines.append("当前主题里没有可引用的上层主张，不能编原理。")
    lines.append("")
    lines.append("【需要时再查】")
    if answer.lookup:
        for ref in answer.lookup:
            lines.append(f"- {ref.label}")
    else:
        lines.append("无")
    lines.append("")
    lines.append("【依据】")
    if answer.evidence:
        for ref in answer.evidence:
            quote = f"「{ref.quote}」" if ref.quote else "见原文定位"
            lines.append(f"- {quote}")
    else:
        lines.append("无")
    lines.append("")
    lines.append("【联想】")
    if answer.transfers:
        for item in answer.transfers:
            lines.append(f"- 这和你已有的「{item.to_label}」是同一类取舍")
    if answer.related:
        for ref in answer.related:
            tag = {"contradicts": "对立", "about": "相关", "related_to": "相邻"}.get(ref.relation or "", "相关")
            lines.append(f"- [{tag}] {ref.label}")
    elif not answer.transfers:
        if answer.unlinked:
            lines.append("图上还没连上相关边。")
        else:
            lines.append("无")
    lines.append("")
    lines.append("【边界】")
    if answer.unknowns:
        for item in answer.unknowns:
            lines.append(f"- {item}")
    elif not answer.direct and not answer.lookup:
        lines.append(f"- {_UNKNOWN}")
    else:
        lines.append("- 以上断言均可点开核对原文。")
    return "\n".join(lines)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
