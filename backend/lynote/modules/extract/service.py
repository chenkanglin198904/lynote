"""Extract claims with locatable source_span. Does not create concepts.

The model may suggest chapter names that already appear in the source.
Code only writes claims. A human hang confirms existing nodes or those names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lynote.contracts.models import ClaimPolarity, Source
from lynote.llm import Completer, LlmError, complete_json, is_configured
from lynote.modules.extract.heuristic import extract_heuristic, upsert_claim
from lynote.modules.extract.spans import locate_span
from lynote.modules.graph.store import InMemoryGraphStore

_POLARITY: set[str] = {"asserts", "denies", "uncertain"}
_SYSTEM = """你是 LyNote 的抽取器。只从原文抽出主张，不要总结成新观点，不要发明原文没有的章名。
每条 claim.quote 必须是原文中的连续片段（可短于整句），不能改写、不能拼接。
找不到原文依据的主张不要输出。
concepts 只填原文中已经出现的连续词，作为「挂到何处」的章名提案，系统不会自动建概念。
只输出 JSON：
{
  "concepts":[{"name":"...","definition":"...","domain":"..."}],
  "claims":[{"text":"...","polarity":"asserts|denies|uncertain","confidence":0.0,"quote":"...","about":["原文中的概念名"]}]
}
最多 8 个概念提案、8 条主张。text 是规范化主张，quote 是原文证据。"""


@dataclass(frozen=True)
class Extraction:
    claim_ids: list[str]
    proposed_names: list[str]


class ExtractService:
    def __init__(self, complete_json: Completer | None = None) -> None:
        self._complete_json = complete_json

    def extract(self, source: Source, store: InMemoryGraphStore) -> Extraction:
        if self._use_model():
            try:
                return self._extract_model(source, store)
            except LlmError:
                if self._complete_json is not None:
                    raise
        return extract_heuristic(source, store)

    def _use_model(self) -> bool:
        return self._complete_json is not None or is_configured()

    def _extract_model(self, source: Source, store: InMemoryGraphStore) -> Extraction:
        completer = self._complete_json or complete_json
        existing = "、".join(concept.name for concept in store.concepts.values()) or "（无）"
        payload = completer(_SYSTEM, _user_prompt(source, existing))
        return apply_extraction(source, store, payload)


def apply_extraction(
    source: Source,
    store: InMemoryGraphStore,
    payload: dict[str, Any],
) -> Extraction:
    text = source.text or source.title
    claim_ids: list[str] = []
    for item in _as_dicts(payload.get("claims"))[:8]:
        quote = str(item.get("quote") or item.get("text") or "").strip()
        span = locate_span(text, quote)
        if span is None:
            continue
        claim_text = str(item.get("text") or quote).strip("。；; ")
        if len(claim_text) < 8:
            continue
        polarity: ClaimPolarity = "asserts"
        raw_polarity = str(item.get("polarity") or "asserts")
        if raw_polarity in _POLARITY:
            polarity = raw_polarity  # type: ignore[assignment]
        try:
            confidence = float(item.get("confidence") or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        quote_in_source = text[span.start : span.end]
        claim_ids.append(
            upsert_claim(
                store,
                source,
                claim_text,
                span,
                quote_in_source,
                polarity=polarity,
                confidence=confidence,
            )
        )
    return Extraction(claim_ids=claim_ids, proposed_names=_proposed_names(source, store, payload))


def _proposed_names(source: Source, store: InMemoryGraphStore, payload: dict[str, Any]) -> list[str]:
    text = source.text or source.title or ""
    blocked = {concept.name for concept in store.concepts.values()}
    blocked.update(goal.title for goal in store.goals.values())
    names: list[str] = []
    for item in _as_dicts(payload.get("concepts"))[:8]:
        names.append(str(item.get("name") or "").strip())
    for item in _as_dicts(payload.get("claims"))[:8]:
        about = item.get("about") or []
        if isinstance(about, list):
            names.extend(str(part).strip() for part in about)
        elif isinstance(about, str):
            names.append(about.strip())
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not name or len(name) < 2 or len(name) > 40:
            continue
        if name in blocked or name in seen:
            continue
        if name not in text:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= 5:
            break
    return out


def _user_prompt(source: Source, existing_concepts: str) -> str:
    body = (source.text or "")[:6000]
    return (
        f"已有概念（尽量复用名称；不要发明原文没有的词）：{existing_concepts}\n\n"
        f"标题：{source.title}\n"
        f"原文：\n{body}"
    )


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
