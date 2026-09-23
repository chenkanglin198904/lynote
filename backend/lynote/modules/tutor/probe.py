"""One Socratic probe after a grounded explanation. Code grades against claims."""

from __future__ import annotations

from lynote.contracts.models import (
    ChatMessage,
    Claim,
    GradeProbeRequest,
    Probe,
    ProbeGrade,
    ProbeOption,
)
from lynote.modules.graph.ids import new_id
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.lexical import coverage
from lynote.modules.retrieve.service import _claim_blob

_TARGET_HIT = 0.22
_CONTRARY_HIT = 0.3
_UNSURE_ID = "opt_unsure"


def attach_probe(message: ChatMessage, store: InMemoryGraphStore) -> ChatMessage:
    if message.probe is not None:
        return message
    if message.grounded is None:
        return message
    target = _target_claim(message, store)
    if target is None:
        return message
    opposed = _opposed(target, store)
    if opposed is not None:
        options = [
            ProbeOption(id=f"opt_{target.id}", label=target.text, claim_id=target.id),
            ProbeOption(id=f"opt_{opposed.id}", label=opposed.text, claim_id=opposed.id),
            ProbeOption(id=_UNSURE_ID, label="我说不清，图上证据不够", claim_id=None),
        ]
        options = sorted(options[:-1], key=lambda item: item.claim_id or "") + options[-1:]
        probe = Probe(
            id=new_id("probe"),
            prompt="刚讲过的点：哪一条是图上已确认、应该按它行动的？另一条是对立主张。",
            kind="choice",
            target_claim_id=target.id,
            options=options,
            status="open",
        )
    else:
        probe = Probe(
            id=new_id("probe"),
            prompt="用自己的话复述刚用到的已确认主张，不要补充图上没有的内容。",
            kind="short",
            target_claim_id=target.id,
            status="open",
        )
    return message.model_copy(update={"probe": probe})


def grade_probe_answer(
    message: ChatMessage,
    payload: GradeProbeRequest,
    store: InMemoryGraphStore,
) -> ChatMessage:
    probe = message.probe
    if probe is None:
        raise KeyError("probe")
    if probe.status == "graded":
        raise ValueError("这道追问已经批改过了")
    target = store.claims.get(probe.target_claim_id)
    if target is None:
        raise KeyError(probe.target_claim_id)
    allowed = set(store.claims)
    if probe.kind == "choice":
        verdict, selected, answer_text = _grade_choice(probe, payload, store)
    else:
        verdict, selected, answer_text = _grade_short(probe, payload, store, target)
    cited = _cited(target, store, verdict)
    cited = [cid for cid in cited if cid in allowed]
    correction = _correction(verdict, target, store)
    grade = ProbeGrade(
        verdict=verdict,
        target_claim_id=target.id,
        cited_claim_ids=cited,
        correction=correction,
        selected_option_id=selected,
        answer_text=answer_text,
    )
    return message.model_copy(
        update={
            "probe": probe.model_copy(update={"status": "graded"}),
            "grade": grade,
        }
    )


def _target_claim(message: ChatMessage, store: InMemoryGraphStore) -> Claim | None:
    assert message.grounded is not None
    confirmed: list[Claim] = []
    fallback: list[Claim] = []
    for ref in [*message.grounded.direct, *message.grounded.lookup]:
        if ref.kind != "claim":
            continue
        claim = store.claims.get(ref.id)
        if claim is None or claim.status == "deprecated":
            continue
        if claim.status == "confirmed":
            confirmed.append(claim)
        elif claim.status != "candidate":
            fallback.append(claim)
    if confirmed:
        return confirmed[0]
    return fallback[0] if fallback else None


def _opposed(claim: Claim, store: InMemoryGraphStore) -> Claim | None:
    for other_id in claim.opposed_claim_ids:
        other = store.claims.get(other_id)
        if other is not None and other.status != "deprecated":
            return other
    for rel in store.relations.values():
        if rel.type != "contradicts":
            continue
        other_id = None
        if rel.from_id == claim.id:
            other_id = rel.to_id
        elif rel.to_id == claim.id:
            other_id = rel.from_id
        other = store.claims.get(other_id) if other_id else None
        if other is not None and other.status != "deprecated":
            return other
    return None


def _grade_choice(
    probe: Probe,
    payload: GradeProbeRequest,
    store: InMemoryGraphStore,
) -> tuple[str, str | None, str | None]:
    option_id = (payload.option_id or "").strip()
    if not option_id:
        raise ValueError("选择题必须点一项")
    option = next((item for item in probe.options if item.id == option_id), None)
    if option is None:
        raise ValueError("选项不在这道追问里")
    if option.claim_id is None:
        return "gap", option.id, option.label
    if option.claim_id == probe.target_claim_id:
        return "correct", option.id, option.label
    target = store.claims[probe.target_claim_id]
    opposed = _opposed(target, store)
    if opposed is not None and option.claim_id == opposed.id:
        return "contrary", option.id, option.label
    return "gap", option.id, option.label


def _grade_short(
    probe: Probe,
    payload: GradeProbeRequest,
    store: InMemoryGraphStore,
    target: Claim,
) -> tuple[str, str | None, str | None]:
    text = (payload.text or "").strip()
    if not text:
        raise ValueError("作答不能空")
    target_score = coverage(text, _claim_blob(target))
    opposed = _opposed(target, store)
    opposed_score = coverage(text, _claim_blob(opposed)) if opposed is not None else 0.0
    if opposed is not None and opposed_score >= _CONTRARY_HIT and opposed_score > target_score:
        return "contrary", None, text
    if target_score >= _TARGET_HIT:
        return "correct", None, text
    return "gap", None, text


def _cited(target: Claim, store: InMemoryGraphStore, verdict: str) -> list[str]:
    ids = [target.id]
    opposed = _opposed(target, store)
    if opposed is not None and verdict == "contrary":
        ids.append(opposed.id)
    return ids


def _correction(verdict: str, target: Claim, store: InMemoryGraphStore) -> str:
    quote = target.evidence[0].quote if target.evidence else None
    evidence = f"依据：「{quote}」" if quote else "依据见图上该主张的出处。"
    opposed = _opposed(target, store)
    if verdict == "correct":
        return f"对。图上已确认的是：{target.text}。{evidence}"
    if verdict == "contrary":
        opposed_text = opposed.text if opposed is not None else "对立主张"
        return (
            f"反了。你靠近的是对立侧「{opposed_text}」。"
            f"图上应按已确认主张：{target.text}。{evidence}"
        )
    return f"漏了要点。图上已确认的是：{target.text}。{evidence}你的回答没有覆盖这条主张。"
