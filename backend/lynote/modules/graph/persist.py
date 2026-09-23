"""Sidecar JSON for inbox / messages / current brief / practice / profile / hangs / brief_touched_at / layer_overrides / play_context."""

from __future__ import annotations

import json
from pathlib import Path

from lynote.contracts.models import (
    ChatMessage,
    DecisionBrief,
    HangProposal,
    InboxItem,
    PracticeStat,
    Profile,
)


def load_workspace_state(
    path: Path,
) -> tuple[
    dict[str, InboxItem],
    list[ChatMessage],
    DecisionBrief | None,
    dict[str, PracticeStat],
    Profile,
    list[HangProposal],
    str | None,
    str | None,
    dict[str, str],
    dict[str, str] | None,
]:
    if not path.exists():
        return {}, [], None, {}, Profile(), [], None, None, {}, None
    raw = json.loads(path.read_text(encoding="utf-8"))
    inbox = {
        item["id"]: InboxItem.model_validate(item) for item in raw.get("inbox", [])
    }
    messages = [
        _migrate_message(ChatMessage.model_validate(item)) for item in raw.get("messages", [])
    ]
    brief_raw = raw.get("brief")
    brief = DecisionBrief.model_validate(brief_raw) if brief_raw else None
    practice: dict[str, PracticeStat] = {}
    for item in raw.get("practice") or []:
        stat = PracticeStat.model_validate(item)
        practice[f"{stat.goal_id}:{stat.claim_id}"] = stat
    profile = Profile.model_validate(raw.get("profile") or {})
    hangs = [HangProposal.model_validate(item) for item in raw.get("hangs") or []]
    touched = raw.get("brief_touched_at")
    goal_id = raw.get("brief_touched_goal_id")
    layer_overrides = {
        key: value
        for key, value in (raw.get("layer_overrides") or {}).items()
        if isinstance(key, str) and value in {"keep", "lookup"}
    }
    play_raw = raw.get("play_context") or {}
    play_context = None
    if isinstance(play_raw, dict) and play_raw.get("play_id") in {"read_article", "after_meeting"}:
        at = play_raw.get("at")
        play_goal = play_raw.get("goal_id")
        play_context = {
            "play_id": play_raw["play_id"],
            "at": at if isinstance(at, str) and at.strip() else "",
            "goal_id": play_goal if isinstance(play_goal, str) and play_goal.strip() else "",
        }
    return (
        inbox,
        messages,
        brief,
        practice,
        profile,
        hangs,
        touched if isinstance(touched, str) and touched.strip() else None,
        goal_id if isinstance(goal_id, str) and goal_id.strip() else None,
        layer_overrides,
        play_context,
    )


def save_workspace_state(
    path: Path,
    inbox: dict[str, InboxItem],
    messages: list[ChatMessage],
    brief: DecisionBrief | None,
    practice: dict[str, PracticeStat] | None = None,
    profile: Profile | None = None,
    hangs: list[HangProposal] | None = None,
    brief_touched_at: str | None = None,
    brief_touched_goal_id: str | None = None,
    layer_overrides: dict[str, str] | None = None,
    play_context: dict[str, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "inbox": [item.model_dump() for item in inbox.values()],
        "messages": [item.model_dump() for item in messages],
        "brief": brief.model_dump() if brief else None,
        "practice": [item.model_dump() for item in (practice or {}).values()],
        "profile": (profile or Profile()).model_dump(),
        "hangs": [item.model_dump() for item in (hangs or [])],
        "brief_touched_at": brief_touched_at,
        "brief_touched_goal_id": brief_touched_goal_id,
        "layer_overrides": layer_overrides or {},
        "play_context": play_context,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _migrate_message(message: ChatMessage) -> ChatMessage:
    if message.lane == "decision":
        return message
    if message.grounded is None and message.probe is None and (
        message.content.startswith("已把决策") or message.content.startswith("已把事后")
    ):
        return message.model_copy(update={"lane": "decision"})
    return message
