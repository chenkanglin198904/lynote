"""Deterministic gate rules. Used when no LLM key, and as hard overrides."""

from __future__ import annotations

from lynote.contracts.models import GateCheck, Goal, Source

_JUNK_HINTS = ("十大", "神器", "必看", "listicle", "收藏即学会", "一键")
_SIGNAL_HINTS = ("知识图谱", "笔记", "主张", "证据", "召回", "决策", "graphrag", "筛选")


def heuristic_checks(
    source: Source,
    goals: list[Goal],
    existing_titles: list[str],
) -> list[GateCheck]:
    text = f"{source.title}\n{source.text or ''}"
    return [
        goal_alignment(text, goals),
        quality(text, kind=source.kind),
        novelty(source.title, existing_titles),
        actionability(text),
        maintenance(text),
    ]


def goal_alignment(text: str, goals: list[Goal]) -> GateCheck:
    blob = text.lower()
    if not goals:
        return GateCheck(
            gate="goal_alignment",
            passed=False,
            note="没有活跃目标，拒绝盲目入库",
        )
    hits: list[str] = []
    for goal in goals:
        haystack = f"{goal.title} {goal.question}".lower()
        keywords = [hint for hint in _SIGNAL_HINTS if hint in haystack]
        keywords.extend(_tokenize(haystack))
        if any(keyword and keyword in blob for keyword in keywords):
            hits.append(goal.title)
    if hits:
        return GateCheck(
            gate="goal_alignment",
            passed=True,
            note=f"命中目标：{'、'.join(hits)}",
        )
    return GateCheck(
        gate="goal_alignment",
        passed=False,
        note="与当前目标无明显重叠",
    )


def quality(text: str, *, kind: str = "") -> GateCheck:
    if any(hint in text for hint in _JUNK_HINTS):
        return GateCheck(
            gate="quality",
            passed=False,
            note="营销/清单体信号，论证密度不足",
        )
    body = text.strip()
    min_len = 8 if kind in {"note", "audio", "video"} else 40
    if len(body) < min_len:
        return GateCheck(
            gate="quality",
            passed=False,
            note="文本过短，无法核验主张",
        )
    if kind in {"note", "audio", "video"}:
        return GateCheck(
            gate="quality",
            passed=True,
            note="亲手材料原文即证据，可定位 source_span",
        )
    return GateCheck(gate="quality", passed=True, note="长度与措辞暂未触发垃圾规则")


def novelty(title: str, existing_titles: list[str]) -> GateCheck:
    compact = _compact(title)
    for other in existing_titles:
        if compact and compact == _compact(other):
            return GateCheck(
                gate="novelty",
                passed=False,
                note=f"与已有来源标题重复：{other}",
            )
    return GateCheck(gate="novelty", passed=True, note="标题相对已有来源是新的")


def actionability(text: str) -> GateCheck:
    if any(hint in text.lower() for hint in _SIGNAL_HINTS):
        return GateCheck(
            gate="actionability",
            passed=True,
            note="可能改变学习路径或技术方案选择",
        )
    return GateCheck(
        gate="actionability",
        passed=False,
        note="看不出能更新哪个选项或下一步",
    )


def maintenance(text: str) -> GateCheck:
    if any(hint in text for hint in _JUNK_HINTS):
        return GateCheck(
            gate="maintenance_cost",
            passed=False,
            note="噪声实体风险高，入库后难消歧",
        )
    return GateCheck(
        gate="maintenance_cost",
        passed=True,
        note="结构尚可，维护成本可接受",
    )


def _tokenize(text: str) -> list[str]:
    tokens = []
    for raw in text.replace("？", " ").replace("?", " ").replace("，", " ").split():
        token = raw.strip().lower()
        if len(token) >= 2:
            tokens.append(token)
    return tokens


def _compact(text: str) -> str:
    return "".join(text.lower().split())
