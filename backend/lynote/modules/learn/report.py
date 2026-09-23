"""Weekly markdown report. Only cites ids that already exist on the graph."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lynote.contracts.models import InboxItem, TopicLearn, WeeklyReport
from lynote.modules.graph.store import InMemoryGraphStore


def compose_weekly_report(
    store: InMemoryGraphStore,
    *,
    inbox: list[InboxItem],
    learn: TopicLearn | None,
    now: datetime | None = None,
) -> WeeklyReport:
    stamp = now or datetime.now(timezone.utc)
    start = (stamp - timedelta(days=7)).date().isoformat()
    source_ids: list[str] = []
    claim_ids: list[str] = []
    lines = [f"# 本周外脑 · {stamp.date().isoformat()}", ""]
    lines.append("只列出图上已有节点。没有出处的结论不会出现。")
    lines.append("")

    lines.append("## 本周记下的来源")
    week_sources = [
        source
        for source in store.sources.values()
        if (source.created_at or "")[:10] >= start
    ]
    if not week_sources:
        lines.append("没有新来源。")
    for source in week_sources:
        source_ids.append(source.id)
        lines.append(f"- {source.kind} `{source.id}` {source.title}")
        for rel in store.relations.values():
            if rel.type == "evidenced_by" and rel.to_id == source.id and rel.from_id in store.claims:
                claim = store.claims[rel.from_id]
                if claim.id not in claim_ids:
                    claim_ids.append(claim.id)
                lines.append(f"  - 主张 `{claim.id}` {claim.text}")
    lines.append("")

    lines.append("## 决策与复盘")
    decision_ids: list[str] = []
    decided = [
        decision
        for decision in store.decisions.values()
        if decision.status in {"committed", "reviewed"}
    ]
    if not decided:
        lines.append("没有已拍板的决策。")
    for decision in decided:
        decision_ids.append(decision.id)
        chosen = next(
            (option.label for option in decision.options if option.id == decision.chosen_option_id),
            "未选",
        )
        lines.append(f"- `{decision.id}` {decision.question} → {chosen}（{decision.status}）")
        if decision.outcome:
            lines.append(f"  - 结果：{decision.outcome}")
    lines.append("")

    lines.append("## 到期巩固")
    reviews = [item for item in (learn.reviews if learn else []) if item.due]
    if not reviews:
        lines.append("没有到期巩固题。")
    for item in reviews:
        if item.claim_id not in claim_ids and item.claim_id in store.claims:
            claim_ids.append(item.claim_id)
        lines.append(f"- `{item.claim_id}` {item.label}")
    lines.append("")

    lines.append("## 缺口")
    gaps = list(learn.gaps) if learn else []
    if not gaps:
        lines.append("没有标出缺口。先学已有点。")
    for gap in gaps[:8]:
        lines.append(f"- `{gap.id}` {gap.advice}")

    pending = [item for item in inbox if item.status == "pending"]
    if pending:
        lines.append("")
        lines.append("## 待审")
        for item in pending[:8]:
            lines.append(f"- `{item.id}` {item.title}")

    known_claims = [cid for cid in claim_ids if cid in store.claims]
    known_sources = [sid for sid in source_ids if sid in store.sources]
    known_decisions = [did for did in decision_ids if did in store.decisions]
    return WeeklyReport(
        title=f"本周外脑 {stamp.date().isoformat()}",
        markdown="\n".join(lines).strip() + "\n",
        claim_ids=known_claims,
        source_ids=known_sources,
        decision_ids=known_decisions,
    )
