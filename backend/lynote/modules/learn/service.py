"""Code-adjudicated mastery. Sidecar practice stats; graph only supplies structure."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lynote.contracts.models import (
    ChatMessage,
    Claim,
    ContrastCard,
    GapAdvice,
    GateCheck,
    InboxItem,
    MasteryItem,
    PracticeStat,
    ReviewItem,
    Source,
    TopicLearn,
)
from lynote.modules.gate.heuristic import _JUNK_HINTS
from lynote.modules.gate.service import verdict_from_checks
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.lexical import coverage
from lynote.modules.tutor.grounded import compose_grounded_answer

_MASTER_CORRECT = 2
_INTERVALS = (0, 1, 3, 7)
_USE_WINDOW_SECONDS = 600
_OPPOSE_HINTS = ("对立", "反对", "相反", "冲突", "不是", "vs", "VS", "反例")
_EVIDENCE_HINTS = ("原文", "证据", "出处", "论文", "source_span", "引用")


def compose_learn(
    store: InMemoryGraphStore,
    practice: dict[str, PracticeStat],
    *,
    goal_id: str | None,
    allowed_ids: set[str] | None,
    now: str | None = None,
) -> TopicLearn:
    when = now or _now()
    claims = [
        claim
        for claim in store.claims.values()
        if claim.status not in {"deprecated", "candidate"}
        and (allowed_ids is None or claim.id in allowed_ids)
    ]
    concepts = [
        concept
        for concept in store.concepts.values()
        if allowed_ids is None or concept.id in allowed_ids
    ]
    claim_items = [_claim_item(claim, store, practice, goal_id) for claim in claims]
    concept_items = [_concept_item(concept.id, concept.name, store, claim_items, allowed_ids) for concept in concepts]

    deep = [item for item in claim_items if _structurally_deep(store.claims[item.id], store)]
    depth = (len(deep) / len(claim_items)) if claim_items else 0.0
    with_claims = [item for item in concept_items if item.claim_ids]
    breadth = (len(with_claims) / len(concept_items)) if concept_items else 0.0

    contrasts = _contrasts(store, allowed_ids)
    gaps = _gaps(claim_items, concept_items)
    reviews = _reviews(claim_items, practice, goal_id, when)

    counts = {key: 0 for key in ("mastered", "weak", "missing", "ready")}
    for item in claim_items + concept_items:
        counts[item.status] += 1

    return TopicLearn(
        goal_id=goal_id,
        depth=round(depth, 3),
        breadth=round(breadth, 3),
        trend=_trend(depth, breadth),
        mastered=counts["mastered"],
        weak=counts["weak"],
        missing=counts["missing"],
        ready=counts["ready"],
        claims=claim_items,
        concepts=concept_items,
        contrasts=contrasts,
        reviews=reviews,
        gaps=gaps,
    )


def record_practice(
    practice: dict[str, PracticeStat],
    *,
    goal_id: str,
    claim_id: str,
    verdict: str,
    now: str | None = None,
) -> PracticeStat:
    when = now or _now()
    key = _key(goal_id, claim_id)
    stat = practice.get(key) or PracticeStat(goal_id=goal_id, claim_id=claim_id)
    stat.last_practiced_at = when
    if verdict == "correct":
        stat.correct_count += 1
        if stat.correct_count >= _MASTER_CORRECT:
            stat.next_review_at = None
        else:
            stat.interval_index = min(stat.interval_index + 1, len(_INTERVALS) - 1)
            days = _INTERVALS[stat.interval_index]
            stat.next_review_at = when if days == 0 else _plus_days(when, days)
    else:
        if verdict == "contrary":
            stat.contrary_count += 1
        else:
            stat.gap_count += 1
        stat.interval_index = 0
        stat.next_review_at = when
    practice[key] = stat
    return stat


def record_use(
    practice: dict[str, PracticeStat],
    *,
    goal_id: str,
    claim_id: str,
    now: str | None = None,
    window_seconds: int = _USE_WINDOW_SECONDS,
) -> PracticeStat:
    when = now or _now()
    key = _key(goal_id, claim_id)
    stat = practice.get(key) or PracticeStat(goal_id=goal_id, claim_id=claim_id)
    if stat.last_practiced_at and window_seconds > 0:
        elapsed = _seconds_between(stat.last_practiced_at, when)
        if elapsed is not None and 0 <= elapsed < window_seconds:
            return stat
    stat.use_count += 1
    stat.last_practiced_at = when
    if stat.correct_count < _MASTER_CORRECT and not stat.next_review_at:
        stat.next_review_at = when
    practice[key] = stat
    return stat


def score_source(source: Source | None, gaps: list[GapAdvice]) -> tuple[float, str]:
    if source is None:
        return 0.0, "来源不在图上"
    blob = f"{source.title}\n{source.text or ''}"
    if any(hint in blob for hint in _JUNK_HINTS):
        return 0.0, "清单体，对缺口没有贡献"
    if not gaps:
        return 0.0, "当前主题没有登记缺口"
    best = 0.0
    note = "看不出能补哪个缺口"
    for gap in gaps:
        target = f"{gap.label} {gap.advice}"
        score = coverage(target, blob)
        if gap.need == "opposition" and any(hint in blob for hint in _OPPOSE_HINTS):
            score += 0.28
        if gap.need == "evidence" and any(hint in blob for hint in _EVIDENCE_HINTS):
            score += 0.2
        if gap.need == "claim" and coverage(gap.label, blob) >= 0.2:
            score += 0.15
        if score > best:
            best = score
            note = gap.advice
    return min(1.0, round(best, 3)), note


def apply_gap_boost(item: InboxItem, source: Source | None, gaps: list[GapAdvice]) -> InboxItem:
    score, note = score_source(source, gaps)
    checks = list(item.checks)
    quality = next((check for check in checks if check.gate == "quality"), None)
    if score >= 0.28 and quality is not None and quality.passed:
        checks = [
            (
                GateCheck(gate="actionability", passed=True, note=f"[缺口] {note}")
                if check.gate == "actionability"
                else check
            )
            for check in checks
        ]
    return item.model_copy(
        update={
            "checks": checks,
            "verdict": verdict_from_checks(checks) if checks else item.verdict,
            "gap_score": score,
            "gap_note": note,
        }
    )


def rank_inbox(
    items: list[InboxItem],
    store: InMemoryGraphStore,
    gaps: list[GapAdvice],
) -> list[InboxItem]:
    scored = [
        apply_gap_boost(item, store.sources.get(item.source_id), gaps) for item in items
    ]
    pending = [item for item in scored if item.status == "pending"]
    rest = [item for item in scored if item.status != "pending"]
    pending.sort(
        key=lambda item: (
            -item.gap_score,
            0 if item.verdict != "reject" else 1,
            item.title,
        )
    )
    return pending + rest


def start_review_message(
    store: InMemoryGraphStore,
    *,
    claim_id: str,
    pinned: list[str] | None = None,
    practice: dict[str, PracticeStat] | None = None,
    overrides: dict[str, str] | None = None,
) -> ChatMessage:
    claim = store.claims.get(claim_id)
    if claim is None or claim.status in {"deprecated", "candidate"}:
        raise KeyError(claim_id)
    pins = list(pinned or [])
    if claim.id not in pins:
        pins.insert(0, claim.id)
    subgraph = store.neighborhood(claim.id, hops=1)
    return compose_grounded_answer(
        claim.text, subgraph, store, pins, practice=practice, overrides=overrides
    )


def _claim_item(
    claim: Claim,
    store: InMemoryGraphStore,
    practice: dict[str, PracticeStat],
    goal_id: str | None,
) -> MasteryItem:
    opposed = _opposition_ids(claim, store)
    has_evidence = _has_evidence(claim)
    stat = practice.get(_key(goal_id or "", claim.id))
    active_misc = any(
        item.status == "active" and item.claim_id == claim.id and (not goal_id or item.goal_id == goal_id)
        for item in store.misconceptions.values()
    )
    if not has_evidence:
        status, reason = "missing", "没有可定位证据"
    elif not opposed:
        status, reason = "missing", "没有对立主张"
    elif active_misc:
        status, reason = "weak", "反复答反或仍有活跃误区"
    elif stat is not None and stat.correct_count >= _MASTER_CORRECT:
        status, reason = "mastered", "连续答对且无活跃误区"
    elif stat is not None and (stat.contrary_count > 0 or stat.gap_count > 0):
        status, reason = "weak", "反复答反或仍有活跃误区"
    else:
        status, reason = "ready", "有证据也有对立，还没巩固"
    return MasteryItem(
        id=claim.id,
        kind="claim",
        label=claim.text,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        claim_ids=[claim.id],
    )


def _concept_item(
    concept_id: str,
    name: str,
    store: InMemoryGraphStore,
    claim_items: list[MasteryItem],
    allowed_ids: set[str] | None,
) -> MasteryItem:
    linked = _claims_about(store, concept_id, allowed_ids)
    linked_items = [item for item in claim_items if item.id in linked]
    if not linked:
        return MasteryItem(
            id=concept_id,
            kind="concept",
            label=name,
            status="missing",
            reason="孤立概念，还没有主张",
        )
    if not any(_opposition_ids(store.claims[cid], store) for cid in linked):
        return MasteryItem(
            id=concept_id,
            kind="concept",
            label=name,
            status="missing",
            reason="只有主张没有对立",
            claim_ids=list(linked),
        )
    if not any(_has_evidence(store.claims[cid]) for cid in linked):
        return MasteryItem(
            id=concept_id,
            kind="concept",
            label=name,
            status="missing",
            reason="主张没有可定位证据",
            claim_ids=list(linked),
        )
    if any(item.status == "weak" for item in linked_items):
        return MasteryItem(
            id=concept_id,
            kind="concept",
            label=name,
            status="weak",
            reason="下属主张仍薄弱",
            claim_ids=list(linked),
        )
    if linked_items and all(item.status == "mastered" for item in linked_items):
        return MasteryItem(
            id=concept_id,
            kind="concept",
            label=name,
            status="mastered",
            reason="下属已确认主张均已掌握",
            claim_ids=list(linked),
        )
    return MasteryItem(
        id=concept_id,
        kind="concept",
        label=name,
        status="ready",
        reason="已有对立和证据，待巩固",
        claim_ids=list(linked),
    )


def _structurally_deep(claim: Claim, store: InMemoryGraphStore) -> bool:
    return _has_evidence(claim) and bool(_opposition_ids(claim, store))


def _contrasts(store: InMemoryGraphStore, allowed_ids: set[str] | None) -> list[ContrastCard]:
    cards: list[ContrastCard] = []
    seen: set[tuple[str, str]] = set()
    for left, right in store.conflicts():
        if allowed_ids is not None and (left.id not in allowed_ids or right.id not in allowed_ids):
            continue
        key = tuple(sorted((left.id, right.id)))
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            ContrastCard(
                left_id=left.id,
                left_label=left.text,
                right_id=right.id,
                right_label=right.text,
            )
        )
    return cards


def _gaps(claims: list[MasteryItem], concepts: list[MasteryItem]) -> list[GapAdvice]:
    out: list[GapAdvice] = []
    for item in concepts + claims:
        if item.status != "missing":
            continue
        if "孤立" in item.reason:
            need = "claim"
            advice = f"该补「{item.label}」的主张和证据"
        elif "对立" in item.reason:
            need = "opposition"
            advice = f"该补「{item.label}」的对立观点"
        else:
            need = "evidence"
            advice = f"该补「{item.label}」的原始出处"
        out.append(
            GapAdvice(
                id=item.id,
                kind=item.kind,
                label=item.label,
                need=need,  # type: ignore[arg-type]
                advice=advice,
            )
        )
    return out


def _reviews(
    claims: list[MasteryItem],
    practice: dict[str, PracticeStat],
    goal_id: str | None,
    now: str,
) -> list[ReviewItem]:
    due: list[ReviewItem] = []
    for item in claims:
        if item.status == "mastered":
            continue
        stat = practice.get(_key(goal_id or "", item.id))
        used = bool(stat and stat.use_count > 0)
        weak = item.status == "weak"
        if not weak and not used:
            continue
        next_at = stat.next_review_at if stat and stat.next_review_at else now
        if next_at > now:
            continue
        reason = "用过，该巩固" if used and not weak else item.reason
        due.append(
            ReviewItem(
                claim_id=item.id,
                label=item.label,
                due=True,
                reason=reason,
                next_review_at=next_at,
            )
        )
    return due


def _trend(depth: float, breadth: float) -> str:
    if not depth and not breadth:
        return "这个主题还没有可学的主张，先入库。"
    if depth < 0.4:
        return "对立或证据不足，还在变浅；先补冲突再刷掌握。"
    if breadth > depth + 0.15:
        return "概念铺得比对立快，这周更像在变宽。"
    return "深度跟上了广度，可以把薄弱点拿来巩固。"


def _opposition_ids(claim: Claim, store: InMemoryGraphStore) -> set[str]:
    ids = set(claim.opposed_claim_ids)
    for rel in store.relations.values():
        if rel.type != "contradicts":
            continue
        if rel.from_id == claim.id:
            ids.add(rel.to_id)
        elif rel.to_id == claim.id:
            ids.add(rel.from_id)
    return {item for item in ids if item in store.claims}


def _has_evidence(claim: Claim) -> bool:
    return any(item.source_span is not None for item in claim.evidence)


def _claims_about(store: InMemoryGraphStore, concept_id: str, allowed_ids: set[str] | None) -> list[str]:
    ids: list[str] = []
    for rel in store.relations.values():
        if rel.type != "about":
            continue
        other = None
        if rel.to_id == concept_id and rel.from_id in store.claims:
            other = rel.from_id
        elif rel.from_id == concept_id and rel.to_id in store.claims:
            other = rel.to_id
        if other is None:
            continue
        if allowed_ids is not None and other not in allowed_ids:
            continue
        if store.claims[other].status in {"deprecated", "candidate"}:
            continue
        ids.append(other)
    return ids


def _key(goal_id: str, claim_id: str) -> str:
    return f"{goal_id}:{claim_id}"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _plus_days(stamp: str, days: int) -> str:
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(days=days)).replace(microsecond=0).isoformat()


def _seconds_between(start: str, end: str) -> float | None:
    try:
        left = datetime.fromisoformat(start)
        right = datetime.fromisoformat(end)
    except ValueError:
        return None
    if left.tzinfo is None:
        left = left.replace(tzinfo=timezone.utc)
    if right.tzinfo is None:
        right = right.replace(tzinfo=timezone.utc)
    return (right - left).total_seconds()
