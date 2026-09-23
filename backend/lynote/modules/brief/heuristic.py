"""Rule fallback for decision briefs. Options may only cite claims in the subgraph."""

from __future__ import annotations

from lynote.contracts.models import Claim, DecisionOption
from lynote.modules.graph.ids import new_id


def compose_heuristic(
    question: str,
    claims: list[Claim],
    conflicts: list[tuple[Claim, Claim]],
) -> tuple[list[DecisionOption], list[str], list[str], str, str | None]:
    if not claims:
        return (
            [],
            [],
            ["召回未命中任何带证据的主张"],
            "没有证据就列出选项，等于编造节点。",
            "先补材料或钉住图上的主张，再生成简报。",
        )

    options: list[DecisionOption] = []
    used: set[str] = set()
    for left, right in conflicts:
        if left.id not in used:
            options.append(_option_from_claim(left, stance="对立主张之一"))
            used.add(left.id)
        if right.id not in used:
            options.append(_option_from_claim(right, stance="对立主张之一"))
            used.add(right.id)
        if len(options) >= 3:
            break

    leftover = [
        claim
        for claim in claims
        if claim.id not in used and claim.status in {"confirmed", "candidate"}
    ]
    if leftover and len(options) < 3:
        options.append(
            DecisionOption(
                id=new_id("opt"),
                label="按其余已确认证据行动",
                summary="；".join(_label(claim.text, 24) for claim in leftover[:3]),
                supporting_claim_ids=[claim.id for claim in leftover[:4]],
            )
        )
        used.update(claim.id for claim in leftover[:4])

    if not options:
        lead = claims[0]
        options.append(_option_from_claim(lead, stance="当前仅有的证据方向"))
        used.add(lead.id)

    options = options[:3]
    evidence_ids = [claim_id for option in options for claim_id in option.supporting_claim_ids]
    disputed = [claim for claim in claims if claim.status == "disputed" or claim.opposed_claim_ids]
    skeptic = (
        f"最强反对来自「{_label(disputed[0].text, 40)}」。若这条成立，上面的推荐就该撤回。"
        if disputed
        else "子图里还没有显式反方。不代表没有风险，只代表当前证据没把它写出来。"
    )
    unknowns = ["简报只基于当前召回子图，图外材料和未过闸文本未计入"]
    if not conflicts:
        unknowns.append("未检索到互相打架的主张，选项可能不完整")
    recommendation = _recommend(options, claims)
    return options, _unique(evidence_ids), unknowns, skeptic, recommendation


def _option_from_claim(claim: Claim, stance: str) -> DecisionOption:
    quote = claim.evidence[0].quote if claim.evidence else claim.text
    return DecisionOption(
        id=new_id("opt"),
        label=_label(claim.text),
        summary=f"{stance}。证据：{quote}",
        supporting_claim_ids=[claim.id],
    )


def _recommend(options: list[DecisionOption], claims: list[Claim]) -> str | None:
    by_id = {claim.id: claim for claim in claims}
    best: tuple[float, DecisionOption] | None = None
    for option in options:
        supported = [by_id[cid] for cid in option.supporting_claim_ids if cid in by_id]
        if not supported:
            continue
        score = sum(
            claim.confidence * (1.2 if claim.status == "confirmed" else 0.6)
            for claim in supported
        ) / len(supported)
        if best is None or score > best[0]:
            best = (score, option)
    if best is None:
        return None
    return f"按当前子图证据，更站得住的是「{best[1].label}」。人仍需拍板；AI 不替你决定。"


def _label(text: str, limit: int = 28) -> str:
    compact = text.strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
