"""Decision brief + skeptic. Consumes a retrieve subgraph. Must not run swarm simulation.

The model may write labels and the skeptic paragraph. supporting_claim_ids must already
exist in the subgraph; invented ids are dropped. Verdict/commit stays with the human.
"""

from __future__ import annotations

from typing import Any

from lynote.contracts.models import (
    Claim,
    Decision,
    DecisionBrief,
    DecisionOption,
    Goal,
    GraphSnapshot,
    Relation,
)
from lynote.llm import Completer, LlmError, complete_json, is_configured
from lynote.modules.brief.heuristic import compose_heuristic
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore

_SYSTEM = """你是 LyNote 的决策简报员，不是预测引擎。
只根据给定主张写一页简报：2–3 个互斥选项、一段反方、若干未知项。
硬规则：
- supporting_claim_ids 只能使用我提供的 claim id，禁止编造
- 每个选项至少引用一条主张
- 反方必须站在对立或 disputed 主张上说话，不要编新事实
- 证据不足就写进 unknowns，不要用想象补齐
- 不要做千人社会模拟
只输出 JSON：
{"options":[{"label":"...","summary":"...","supporting_claim_ids":["claim_x"]}],"skeptic":"...","unknowns":["..."],"recommendation":"..."}
"""


class BriefService:
    def __init__(self, complete_json: Completer | None = None) -> None:
        self._complete_json = complete_json

    def compose(
        self,
        question: str,
        subgraph: GraphSnapshot,
        store: InMemoryGraphStore,
        *,
        goal: Goal | None = None,
        decision: Decision | None = None,
        brief_id: str | None = None,
        use_model: bool = True,
    ) -> DecisionBrief:
        claims = _claims_in(subgraph, store)
        allowed = {claim.id for claim in claims}
        conflicts = [
            pair
            for pair in store.conflicts()
            if pair[0].id in allowed and pair[1].id in allowed
        ]
        options, evidence_ids, unknowns, skeptic, recommendation = compose_heuristic(
            question, claims, conflicts
        )
        engine = "规则"
        if use_model and self._use_model() and claims:
            try:
                modeled = self._model_draft(question, claims, conflicts)
                options, evidence_ids, unknowns, skeptic, recommendation = _merge_model(
                    modeled, allowed, claims, conflicts
                )
                engine = "模型"
            except LlmError:
                engine = "规则"
        if engine == "规则":
            skeptic = f"[规则] {skeptic}"
        else:
            skeptic = skeptic if skeptic.startswith("[") else f"[模型] {skeptic}"

        decision = self._upsert_decision(store, question, options, goal, decision)
        if goal is not None:
            _ensure_decides(store, decision.id, goal.id)
        return bind_brief(
            DecisionBrief(
                id=brief_id or new_id("brief"),
                decision_id=decision.id,
                question=question,
                options=options,
                evidence_claim_ids=evidence_ids,
                unknowns=unknowns,
                skeptic=skeptic,
                recommendation=recommendation,
            ),
            decision,
        )

    def commit(
        self,
        brief: DecisionBrief,
        option_id: str,
        rationale: str | None,
        store: InMemoryGraphStore,
    ) -> DecisionBrief:
        decision = store.decisions[brief.decision_id]
        if decision.status == "reviewed":
            raise ValueError("已复盘的决策不能再改选项，请重算简报开新决策")
        if option_id not in {option.id for option in decision.options}:
            raise KeyError(option_id)
        reason = (rationale or "").strip()
        if not reason:
            raise ValueError("采纳时必须写下理由，不能空着点选项")
        decision.chosen_option_id = option_id
        decision.rationale = reason
        decision.status = "committed"
        store.upsert_decision(decision)
        return bind_brief(brief, decision)

    def review(self, brief: DecisionBrief, outcome: str, store: InMemoryGraphStore) -> DecisionBrief:
        text = outcome.strip()
        if not text:
            raise ValueError("复盘不能是空的。写事后真实发生了什么。")
        decision = store.decisions.get(brief.decision_id)
        if decision is None:
            raise KeyError(brief.decision_id)
        if decision.status not in {"committed", "reviewed"}:
            raise ValueError("只能给已采纳的决策写复盘")
        decision.outcome = text
        decision.status = "reviewed"
        store.upsert_decision(decision)
        return bind_brief(brief, decision)

    def _use_model(self) -> bool:
        return self._complete_json is not None or is_configured()

    def _model_draft(
        self,
        question: str,
        claims: list[Claim],
        conflicts: list[tuple[Claim, Claim]],
    ) -> dict[str, Any]:
        completer = self._complete_json or complete_json
        return completer(_SYSTEM, _user_prompt(question, claims, conflicts))

    def _upsert_decision(
        self,
        store: InMemoryGraphStore,
        question: str,
        options: list[DecisionOption],
        goal: Goal | None,
        decision: Decision | None,
    ) -> Decision:
        if decision is None or decision.status in {"committed", "reviewed"}:
            decision = Decision(
                id=new_id("decision"),
                goal_id=goal.id if goal else "",
                question=question,
                options=options,
                status="draft",
            )
        else:
            decision.question = question
            decision.options = options
            decision.chosen_option_id = None
            decision.rationale = None
            decision.outcome = None
            decision.status = "draft"
        return store.upsert_decision(decision)


def bind_brief(brief: DecisionBrief, decision: Decision | None) -> DecisionBrief:
    if decision is None:
        return brief
    return brief.model_copy(
        update={
            "chosen_option_id": decision.chosen_option_id,
            "rationale": decision.rationale,
            "outcome": decision.outcome,
        }
    )


def _claims_in(subgraph: GraphSnapshot, store: InMemoryGraphStore) -> list[Claim]:
    claims: list[Claim] = []
    for node in subgraph.nodes:
        if node.kind != "claim":
            continue
        claim = store.claims.get(node.id)
        if claim is not None:
            claims.append(claim)
    return claims


def _merge_model(
    payload: dict[str, Any],
    allowed: set[str],
    claims: list[Claim],
    conflicts: list[tuple[Claim, Claim]],
) -> tuple[list[DecisionOption], list[str], list[str], str, str | None]:
    fallback = compose_heuristic("", claims, conflicts)
    raw_options = payload.get("options")
    options: list[DecisionOption] = []
    if isinstance(raw_options, list):
        for item in raw_options[:3]:
            if not isinstance(item, dict):
                continue
            ids = [
                str(cid)
                for cid in (item.get("supporting_claim_ids") or [])
                if str(cid) in allowed
            ]
            if not ids:
                continue
            label = str(item.get("label") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not label:
                continue
            options.append(
                DecisionOption(
                    id=new_id("opt"),
                    label=label[:40],
                    summary=summary[:160] or "见引用主张",
                    supporting_claim_ids=ids,
                )
            )
    if not options:
        return fallback
    evidence = []
    for option in options:
        evidence.extend(option.supporting_claim_ids)
    unknowns_raw = payload.get("unknowns")
    unknowns = (
        [str(item).strip() for item in unknowns_raw if str(item).strip()]
        if isinstance(unknowns_raw, list)
        else fallback[2]
    )
    if not unknowns:
        unknowns = fallback[2]
    skeptic = str(payload.get("skeptic") or "").strip() or fallback[3]
    recommendation = str(payload.get("recommendation") or "").strip() or fallback[4]
    return options, _unique(evidence), unknowns[:6], skeptic, recommendation


def _user_prompt(
    question: str,
    claims: list[Claim],
    conflicts: list[tuple[Claim, Claim]],
) -> str:
    lines = [f"问题：{question}", "", "可用主张（只能引用这些 id）："]
    for claim in claims:
        quote = claim.evidence[0].quote if claim.evidence else ""
        opposed = ",".join(claim.opposed_claim_ids) or "无"
        lines.append(
            f"- {claim.id} [{claim.status}] {claim.text} | 对立:{opposed} | 出处:{quote}"
        )
    if conflicts:
        lines.append("")
        lines.append("已知冲突对：")
        for left, right in conflicts:
            lines.append(f"- {left.id} contradicts {right.id}")
    return "\n".join(lines)


def _ensure_decides(store: InMemoryGraphStore, decision_id: str, goal_id: str) -> None:
    for rel in store.relations.values():
        if rel.type == "decides" and rel.from_id == decision_id and rel.to_id == goal_id:
            return
    store.upsert_relation(
        Relation(
            id=new_id("rel"),
            from_id=decision_id,
            to_id=goal_id,
            type="decides",
        )
    )


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
