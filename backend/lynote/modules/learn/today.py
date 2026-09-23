"""Today board: due reviews, pending inbox, open decisions, today's notes."""

from __future__ import annotations

from datetime import datetime, timezone

from lynote.contracts.models import Goal, InboxItem, TodayBoard, TodayItem, TopicLearn
from lynote.modules.graph.store import InMemoryGraphStore


def compose_today(
    store: InMemoryGraphStore,
    *,
    inbox: list[InboxItem],
    learn: TopicLearn | None,
    goal: Goal | None = None,
    allowed_ids: set[str] | None = None,
    brief_touched_at: datetime | None = None,
    brief_touched_goal_id: str | None = None,
    now: datetime | None = None,
) -> TodayBoard:
    stamp = now or datetime.now(timezone.utc)
    day = stamp.date().isoformat()
    reviews = [
        TodayItem(kind="review", id=item.claim_id, title=item.label, detail=item.reason)
        for item in (learn.reviews if learn else [])
        if item.due
    ]
    pending = [
        TodayItem(kind="inbox", id=item.id, title=item.title, detail=item.verdict)
        for item in inbox
        if item.status == "pending"
    ]
    goal_id = goal.id if goal is not None else None
    waiting: list[TodayItem] = []
    drafts: list[TodayItem] = []
    show_draft = _same_iso_week(brief_touched_at, stamp) and (
        goal_id is None or brief_touched_goal_id == goal_id
    )
    for decision in store.decisions.values():
        if goal_id and decision.goal_id != goal_id:
            continue
        if decision.status == "committed" and not (decision.outcome or "").strip():
            waiting.append(
                TodayItem(
                    kind="decision",
                    id=decision.id,
                    title=decision.question,
                    detail="已拍板，待复盘",
                )
            )
        elif decision.status == "draft" and show_draft:
            drafts.append(
                TodayItem(
                    kind="decision",
                    id=decision.id,
                    title=decision.question,
                    detail="简报未拍板",
                )
            )
    notes: list[TodayItem] = []
    for source in store.sources.values():
        if source.kind not in {"note", "audio", "video"}:
            continue
        if allowed_ids is not None and source.id not in allowed_ids:
            continue
        created = (source.created_at or "")[:10]
        if created != day:
            continue
        notes.append(TodayItem(kind="note", id=source.id, title=source.title, detail=source.kind))
    return TodayBoard(
        reviews=reviews[:8],
        inbox=pending[:8],
        decisions=(waiting + drafts)[:8],
        notes=notes[:8],
    )


def _same_iso_week(touched: datetime | None, now: datetime) -> bool:
    if touched is None:
        return False
    left = touched.astimezone(timezone.utc) if touched.tzinfo else touched.replace(tzinfo=timezone.utc)
    right = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return left.isocalendar()[:2] == right.isocalendar()[:2]
