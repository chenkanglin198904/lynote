"""Play-context retrieve weights. Same search, different ranking. Does not invent claims."""

from __future__ import annotations

from datetime import datetime, timezone

from lynote.contracts.models import PlayId
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.layers import _has_opposition

_CONCEPT_BOOST = 0.10
_OPPOSE_BOOST = 0.10
_DECISION_BOOST = 0.12
_ACTION_BOOST = 0.08
_PLAY_BOOST_CAP = 0.18
_OWN_NOTE = {"note", "audio", "video"}


def play_boost(store: InMemoryGraphStore, claim_id: str, play_id: PlayId | None) -> float:
    if not play_id:
        return 0.0
    claim = store.claims.get(claim_id)
    if claim is None or claim.status == "deprecated":
        return 0.0
    if play_id == "read_article":
        boost = 0.0
        if _hung_on_concept(store, claim_id):
            boost += _CONCEPT_BOOST
        if _has_opposition(store, claim):
            boost += _OPPOSE_BOOST
        return min(_PLAY_BOOST_CAP, boost)
    if play_id == "after_meeting":
        boost = 0.0
        if _supports_open_decision(store, claim_id):
            boost += _DECISION_BOOST
        if _from_working_note(store, claim):
            boost += _ACTION_BOOST
        return min(_PLAY_BOOST_CAP, boost)
    return 0.0


def context_still_active(
    play_id: str | None,
    at: datetime | None,
    goal_id: str | None,
    *,
    now: datetime | None = None,
    active_goal_id: str | None,
) -> PlayId | None:
    if play_id not in {"read_article", "after_meeting"} or at is None:
        return None
    if goal_id and active_goal_id and goal_id != active_goal_id:
        return None
    stamp = now or datetime.now(timezone.utc)
    left = at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)
    right = stamp.astimezone(timezone.utc) if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    if left.date() != right.date():
        return None
    return play_id  # type: ignore[return-value]


def _hung_on_concept(store: InMemoryGraphStore, claim_id: str) -> bool:
    for rel in store.relations.values():
        if rel.type == "about" and rel.from_id == claim_id and rel.to_id in store.concepts:
            return True
    return False


def _supports_open_decision(store: InMemoryGraphStore, claim_id: str) -> bool:
    for decision in store.decisions.values():
        if decision.status == "reviewed":
            continue
        if decision.status != "committed":
            continue
        if (decision.outcome or "").strip():
            continue
        chosen = decision.chosen_option_id
        for option in decision.options:
            if chosen and option.id != chosen:
                continue
            if claim_id in option.supporting_claim_ids:
                return True
    return False


def _from_working_note(store: InMemoryGraphStore, claim) -> bool:
    for item in claim.evidence:
        source = store.sources.get(item.source_id)
        if source is not None and source.kind in _OWN_NOTE:
            return True
    return False
