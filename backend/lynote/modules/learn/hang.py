"""Propose hanging new claims onto existing concepts, the current goal, or in-source names.

Code scores overlap. Does not invent concept names. A new Concept is created only when
the human confirms a name that already appears in the source and was proposed at extract.
"""

from __future__ import annotations

from lynote.contracts.models import Concept, HangCandidate, HangProposal, Relation
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.lexical import coverage


def propose_hangs(
    store: InMemoryGraphStore,
    *,
    claim_ids: list[str],
    source_id: str,
    inbox_id: str | None,
    goal_id: str | None,
    proposed_names: list[str] | None = None,
) -> HangProposal | None:
    claims = [store.claims[cid] for cid in claim_ids if cid in store.claims]
    if not claims:
        return None
    unlinked = [
        claim
        for claim in claims
        if not _hangs_on_concept(store, claim.id)
    ]
    if not unlinked:
        return None
    blob = " ".join(claim.text for claim in unlinked)
    candidates: list[HangCandidate] = []
    if goal_id and goal_id in store.goals:
        goal = store.goals[goal_id]
        candidates.append(
            HangCandidate(
                node_id=goal.id,
                kind="goal",
                label=goal.title,
                score=1.0,
                reason="当前主题",
            )
        )
    scored: list[HangCandidate] = []
    for concept in store.concepts.values():
        score = max(
            coverage(concept.name, blob),
            coverage(blob, concept.name),
            coverage(concept.definition or "", blob) if concept.definition else 0.0,
        )
        if score < 0.12:
            continue
        scored.append(
            HangCandidate(
                node_id=concept.id,
                kind="concept",
                label=concept.name,
                score=round(score, 3),
                reason="与已有概念名称/定义重叠",
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    candidates.extend(scored[:5])
    return HangProposal(
        source_id=source_id,
        inbox_id=inbox_id,
        claim_ids=[claim.id for claim in unlinked],
        candidates=candidates,
        proposed_names=_clean_proposed(store, source_id, proposed_names or []),
    )


def confirm_hang(
    store: InMemoryGraphStore,
    claim_ids: list[str],
    target_id: str = "",
    *,
    new_name: str = "",
    allowed_names: set[str] | None = None,
    goal_id: str | None = None,
) -> list[Relation]:
    from lynote.modules.learn.outline import capture_to_chapter

    name = (new_name or "").strip()
    target = (target_id or "").strip()
    if name and target:
        raise ValueError("不能同时指定已有节点和新章名")
    if name:
        chapter_id = _create_or_reuse_concept(
            store,
            name,
            claim_ids=claim_ids,
            allowed_names=allowed_names or set(),
            goal_id=goal_id,
        )
        return capture_to_chapter(store, chapter_id=chapter_id, claim_ids=claim_ids)
    if not target:
        raise ValueError("请点已有概念或当前主题，或点原文里出现的新章名")
    return capture_to_chapter(store, chapter_id=target, claim_ids=claim_ids)


def prune_proposal(proposal: HangProposal, store: InMemoryGraphStore) -> HangProposal | None:
    remaining = [
        cid for cid in proposal.claim_ids if cid in store.claims and not _hangs_on_concept(store, cid)
    ]
    if not remaining:
        return None
    names = _clean_proposed(store, proposal.source_id, proposal.proposed_names)
    return proposal.model_copy(update={"claim_ids": remaining, "proposed_names": names})


def _create_or_reuse_concept(
    store: InMemoryGraphStore,
    name: str,
    *,
    claim_ids: list[str],
    allowed_names: set[str],
    goal_id: str | None,
) -> str:
    if name not in allowed_names:
        raise ValueError("只能确认抽取时提议且出现在原文中的章名，不能临时起名")
    if not _name_in_sources(store, claim_ids, name):
        raise ValueError("章名必须是原文中的连续片段")
    existing = next((item for item in store.concepts.values() if item.name == name), None)
    if existing is not None:
        return existing.id
    concept = Concept(id=new_id("concept"), name=name)
    store.upsert_concept(concept)
    if goal_id and goal_id in store.goals:
        store.upsert_relation(
            Relation(
                id=new_id("rel"),
                from_id=concept.id,
                to_id=goal_id,
                type="about",
            )
        )
    return concept.id


def _clean_proposed(store: InMemoryGraphStore, source_id: str, names: list[str]) -> list[str]:
    source = store.sources.get(source_id)
    text = (source.text or source.title or "") if source else ""
    blocked = {concept.name for concept in store.concepts.values()}
    blocked.update(goal.title for goal in store.goals.values())
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = (raw or "").strip()
        if not name or len(name) < 2 or len(name) > 40:
            continue
        if name in blocked or name in seen:
            continue
        if text and name not in text:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= 5:
            break
    return out


def _name_in_sources(store: InMemoryGraphStore, claim_ids: list[str], name: str) -> bool:
    for claim_id in claim_ids:
        claim = store.claims.get(claim_id)
        if claim is None:
            continue
        for evidence in claim.evidence:
            source = store.sources.get(evidence.source_id)
            if source is None:
                continue
            blob = source.text or source.title or ""
            if name in blob:
                return True
    return False


def _hangs_on_concept(store: InMemoryGraphStore, claim_id: str) -> bool:
    for rel in store.relations.values():
        if rel.type not in {"about", "belongs_to"}:
            continue
        if rel.from_id == claim_id and rel.to_id in store.concepts:
            return True
        if rel.to_id == claim_id and rel.from_id in store.concepts:
            return True
    return False
