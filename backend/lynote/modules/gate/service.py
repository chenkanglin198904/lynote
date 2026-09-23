"""Gate scores a source against current goals. Writes inbox verdicts, never the graph.

The model may explain each check. Verdict composition and hard overrides stay in code:
no goals → fail alignment; duplicate title → fail novelty; alignment/quality/novelty
fail → reject; actionability fail → review.
"""

from __future__ import annotations

from typing import Any

from lynote.contracts.models import (
    GateCheck,
    GateName,
    GateVerdict,
    Goal,
    InboxItem,
    Source,
)
from lynote.llm import Completer, LlmError, complete_json, is_configured
from lynote.modules.gate.heuristic import heuristic_checks, novelty as novelty_check
from lynote.modules.graph.ids import new_id

_GATE_ORDER: tuple[GateName, ...] = (
    "goal_alignment",
    "quality",
    "novelty",
    "actionability",
    "maintenance_cost",
)

_SYSTEM = """你是 LyNote 的入库闸门。任务是解释为什么收下或丢掉一份材料，不是写摘要。
必须对下面五道闸逐一给出 passed 与一句可核对的 note（说明依据，不要空话）：
- goal_alignment：是否推进用户当前目标/问题
- quality：是否有可核验论证，而不是营销清单
- novelty：相对已有标题是否只是换皮重复
- actionability：能否改变学习路径或决策选项
- maintenance_cost：入库后是否会制造难消歧的噪声实体

默认偏拒绝。只输出 JSON：
{"checks":[{"gate":"goal_alignment","passed":true,"note":"..."}, ...]}
五道闸必须齐全。note 用中文，不超过 80 字。"""


class GateService:
    def __init__(self, complete_json: Completer | None = None) -> None:
        self._complete_json = complete_json

    def evaluate(
        self,
        source: Source,
        goals: list[Goal],
        existing_titles: list[str],
    ) -> InboxItem:
        fallback = heuristic_checks(source, goals, existing_titles)
        checks = fallback
        engine = "规则"
        if self._use_model():
            try:
                checks = self._model_checks(source, goals, existing_titles, fallback)
                engine = "模型"
            except LlmError:
                checks = fallback
                engine = "规则"
        checks = _apply_hard_overrides(checks, source, goals, existing_titles)
        forced = {"novelty"}
        if not goals:
            forced.add("goal_alignment")
        checks = [
            _mark_engine(check, engine, forced=forced) for check in _ordered(checks)
        ]
        return InboxItem(
            id=new_id("inbox"),
            source_id=source.id,
            title=source.title,
            snippet=_snippet(source),
            status="pending",
            verdict=verdict_from_checks(checks),
            checks=checks,
        )

    def _use_model(self) -> bool:
        return self._complete_json is not None or is_configured()

    def _model_checks(
        self,
        source: Source,
        goals: list[Goal],
        existing_titles: list[str],
        fallback: list[GateCheck],
    ) -> list[GateCheck]:
        completer = self._complete_json or complete_json
        payload = completer(_SYSTEM, _user_prompt(source, goals, existing_titles))
        parsed = _parse_checks(payload)
        by_name = {check.gate: check for check in fallback}
        by_name.update(parsed)
        return [by_name[name] for name in _GATE_ORDER]


def verdict_from_checks(checks: list[GateCheck]) -> GateVerdict:
    by_name = {check.gate: check for check in checks}
    if not by_name["goal_alignment"].passed or not by_name["quality"].passed:
        return "reject"
    if not by_name["novelty"].passed:
        return "reject"
    if not by_name["actionability"].passed:
        return "review"
    return "accept"


def _apply_hard_overrides(
    checks: list[GateCheck],
    source: Source,
    goals: list[Goal],
    existing_titles: list[str],
) -> list[GateCheck]:
    by_name = {check.gate: check for check in checks}
    if not goals:
        by_name["goal_alignment"] = GateCheck(
            gate="goal_alignment",
            passed=False,
            note="没有活跃目标，拒绝盲目入库",
        )
    by_name["novelty"] = novelty_check(source.title, existing_titles)
    if source.kind in {"note", "audio", "video"} and goals and len((source.text or "").strip()) >= 8:
        by_name["goal_alignment"] = GateCheck(
            gate="goal_alignment",
            passed=True,
            note="写入当前主题，人审后抽取",
        )
        by_name["actionability"] = GateCheck(
            gate="actionability",
            passed=True,
            note="可能更新当前主题主张",
        )
    return [by_name[name] for name in _GATE_ORDER]


def _parse_checks(payload: dict[str, Any]) -> dict[GateName, GateCheck]:
    raw_checks = payload.get("checks")
    if not isinstance(raw_checks, list):
        raise LlmError("gate JSON missing checks[]")
    parsed: dict[GateName, GateCheck] = {}
    allowed = set(_GATE_ORDER)
    for item in raw_checks:
        if not isinstance(item, dict):
            continue
        name = item.get("gate")
        if name not in allowed:
            continue
        note = str(item.get("note") or "").strip()
        if not note:
            continue
        parsed[name] = GateCheck(
            gate=name,
            passed=bool(item.get("passed")),
            note=note[:120],
        )
    if len(parsed) < 3:
        raise LlmError("gate JSON too incomplete")
    return parsed


def _user_prompt(source: Source, goals: list[Goal], existing_titles: list[str]) -> str:
    goal_lines = "\n".join(
        f"- {goal.title}：{goal.question}" for goal in goals
    ) or "- （无）"
    titles = "、".join(existing_titles[:12]) or "（无）"
    body = (source.text or "")[:4000]
    return (
        f"当前目标：\n{goal_lines}\n\n"
        f"已有来源标题：{titles}\n\n"
        f"待审材料标题：{source.title}\n"
        f"正文：\n{body}"
    )


def _ordered(checks: list[GateCheck]) -> list[GateCheck]:
    by_name = {check.gate: check for check in checks}
    return [by_name[name] for name in _GATE_ORDER]


def _mark_engine(check: GateCheck, engine: str, forced: set[str]) -> GateCheck:
    label = "规则" if check.gate in forced else engine
    prefix = f"[{label}] "
    note = check.note if check.note.startswith("[") else prefix + check.note
    return check.model_copy(update={"note": note})


def _snippet(source: Source) -> str:
    snippet = (source.text or source.title).strip().replace("\n", " ")
    if len(snippet) > 160:
        return snippet[:157] + "..."
    return snippet
