"""Topic outline from graph structure. Does not invent chapter names."""

from __future__ import annotations

from lynote.contracts.models import OutlineChapter, PracticeStat, Relation, TopicOutline
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.learn.pack import pack_claims

_LINK = {"about", "belongs_to"}


def compose_outline(
    store: InMemoryGraphStore,
    goal_id: str | None,
    practice: dict[str, PracticeStat] | None = None,
    overrides: dict[str, str] | None = None,
) -> TopicOutline:
    if goal_id is None or goal_id not in store.goals:
        return TopicOutline(intro="还没有学习主题。先建一个主题并入库，目录只会从图上已有的概念长出来。")
    goal = store.goals[goal_id]
    allowed = {node.id for node in store.neighborhood(goal_id).nodes}
    concept_ids = [
        concept.id
        for concept in store.concepts.values()
        if concept.id in allowed and _linked(store, concept.id, goal_id)
    ]
    concept_ids.sort(key=lambda cid: store.concepts[cid].name)
    chapters: list[OutlineChapter] = []
    hung: set[str] = set()
    for concept_id in concept_ids:
        concept = store.concepts[concept_id]
        claim_ids = [
            claim.id
            for claim in store.claims.values()
            if claim.id in allowed and _linked(store, claim.id, concept_id)
        ]
        hung.update(claim_ids)
        keep, lookup = pack_claims(store, claim_ids, practice, overrides)
        quotes = [_claim_line(store, cid) for cid in claim_ids[:3]]
        if keep or lookup:
            summary = f"该内化 {len(keep)} 条，可外置 {len(lookup)} 条。"
            extra = concept.definition or ("；".join(quotes) if quotes else "")
            if extra:
                summary = f"{summary} {extra}"
        else:
            summary = concept.definition or "这一章还没有挂上主张，先学目录或补材料。"
        chapters.append(
            OutlineChapter(
                id=concept.id,
                title=concept.name,
                kind="concept",
                summary=summary,
                claim_ids=claim_ids,
                child_count=len(claim_ids),
                pack_keep=keep,
                pack_lookup=lookup,
            )
        )
    loose = [
        claim
        for claim in store.claims.values()
        if claim.id in allowed and claim.id not in hung and claim.status != "deprecated"
    ]
    loose_claims = []
    for claim in loose:
        keep, lookup = pack_claims(store, [claim.id], practice, overrides)
        loose_claims.append(
            OutlineChapter(
                id=claim.id,
                title=claim.text,
                kind="claim",
                summary=_claim_line(store, claim.id),
                claim_ids=[claim.id],
                child_count=0,
                pack_keep=keep,
                pack_lookup=lookup,
            )
        )
    names = [item.title for item in chapters]
    if names:
        intro = f"{goal.title}的目录来自图谱里已有的概念，不另编教材大纲：{'、'.join(names)}。"
    elif loose_claims:
        intro = f"{goal.title}里还没有概念层，下面按已有主张一节一节读。要长成目录，在待挂里点已有概念或原文中的新章名。"
    else:
        intro = f"{goal.question} 图上还没有可拆的章节。先采集并接受抽取。"
    if goal.question:
        intro = f"{goal.question} {intro}"
    return TopicOutline(
        goal_id=goal.id,
        title=goal.title,
        intro=intro.strip(),
        chapters=chapters,
        loose_claims=loose_claims,
    )


def capture_to_chapter(
    store: InMemoryGraphStore,
    *,
    chapter_id: str,
    claim_ids: list[str],
) -> list[Relation]:
    node = store.as_node(chapter_id)
    if node is None:
        raise KeyError(chapter_id)
    if node.kind not in {"concept", "goal"}:
        raise ValueError("只能把主张收入当前章节（概念或主题），不能发明节点")
    written: list[Relation] = []
    existing = {(rel.from_id, rel.to_id, rel.type) for rel in store.relations.values()}
    for claim_id in claim_ids:
        if claim_id not in store.claims:
            continue
        key = (claim_id, chapter_id, "about")
        if key in existing or (chapter_id, claim_id, "about") in existing:
            continue
        relation = store.upsert_relation(
            Relation(
                id=new_id("rel"),
                from_id=claim_id,
                to_id=chapter_id,
                type="about",
            )
        )
        existing.add(key)
        written.append(relation)
        claim = store.claims[claim_id]
        if claim.status == "candidate":
            claim.status = "confirmed"
            store.upsert_claim(claim)
    if not written:
        raise ValueError("没有可收入的已有主张。问答不能在图外编新知识点。")
    return written


def _linked(store: InMemoryGraphStore, left: str, right: str) -> bool:
    for rel in store.relations.values():
        if rel.type not in _LINK:
            continue
        if {rel.from_id, rel.to_id} == {left, right}:
            return True
    return False


def _claim_line(store: InMemoryGraphStore, claim_id: str) -> str:
    claim = store.claims.get(claim_id)
    if claim is None:
        return ""
    quote = claim.evidence[0].quote if claim.evidence else None
    return quote or claim.text
