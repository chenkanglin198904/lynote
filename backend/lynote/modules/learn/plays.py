"""Fixed plays: named recipes over existing ingest / inbox / hang / brief loops.

Not a plugin registry. New plays are code changes, not installable skills.
A play never accepts inbox, never hangs, never invents nodes, and never commits a decision.
"""

from __future__ import annotations

from lynote.contracts.models import InboxItem, Play, PlayContext, PlayId, SourceKind

_READ: tuple[SourceKind, ...] = ("url", "markdown", "pdf")
_MEET: tuple[SourceKind, ...] = ("note", "audio", "video")

PLAYS: tuple[Play, ...] = (
    Play(
        id="read_article",
        title="读完这篇",
        summary="把刚读完的材料送进当前主题。过闸后仍要在下一步里接受并挂上，不会自动建章。",
        steps=["送去过闸", "下一步里接受抽取", "挂到已有概念或当前主题"],
        kinds=list(_READ),
    ),
    Play(
        id="after_meeting",
        title="会后落地",
        summary="把会上的判断记进当前主题。需要拍板时打开简报，仍用图上已有主张，不会替你选。",
        steps=["记下判断", "下一步里接受并挂上", "可选：打开简报拍板"],
        kinds=list(_MEET),
    ),
)

_BY_ID = {item.id: item for item in PLAYS}
_KINDS: dict[PlayId, tuple[SourceKind, ...]] = {
    "read_article": _READ,
    "after_meeting": _MEET,
}
_DEFAULT_KIND: dict[PlayId, SourceKind] = {
    "read_article": "url",
    "after_meeting": "note",
}


def catalog() -> list[Play]:
    return [item.model_copy() for item in PLAYS]


def get_play(play_id: str) -> Play:
    play = _BY_ID.get(play_id)  # type: ignore[arg-type]
    if play is None:
        raise ValueError("没有这个剧本。只内置「读完这篇」和「会后落地」，不能安装插件。")
    return play.model_copy()


def normalize_kind(play_id: PlayId, kind: SourceKind | None) -> SourceKind:
    allowed = _KINDS[play_id]
    picked = kind or _DEFAULT_KIND[play_id]
    if picked not in allowed:
        labels = " / ".join(allowed)
        raise ValueError(f"这个剧本只能用 {labels}，不能改走别的入库路径")
    return picked


def next_hint(play_id: PlayId, item: InboxItem, *, composed: bool) -> str:
    if item.status != "pending":
        return "材料已处理。若还要进图，换一份再走这个剧本。"
    if play_id == "read_article":
        return "材料已过闸，出现在下一步。该拒的拒；该过的点接受，再挂到已有概念或当前主题。"
    if composed:
        return "会上这条在下一步里接受并挂上。简报已按当前主题重算，只用图上已有主张，不会把未过审的会记写进选项。"
    return "会上这条出现在下一步。接受并挂上之后，若要拍板再打开简报。"


def context_hint(play_id: PlayId) -> str:
    if play_id == "read_article":
        return "召回正按「读完这篇」偏概念和对立，今天内有效。"
    return "召回正按「会后落地」偏未复盘决策和可行动主张，今天内有效。"


def compose_play_context(play_id: PlayId, at: str) -> PlayContext:
    play = get_play(play_id)
    return PlayContext(play_id=play.id, title=play.title, hint=context_hint(play.id), at=at)
