"""Surface past decisions when a similar question comes back."""

from __future__ import annotations

from lynote.contracts.models import PriorDecisionRef
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.lexical import coverage

_MIN = 0.18


def find_prior_decisions(
    store: InMemoryGraphStore,
    question: str,
    *,
    exclude_id: str | None = None,
    limit: int = 3,
) -> list[PriorDecisionRef]:
    query = question.strip()
    if not query:
        return []
    ranked: list[tuple[float, PriorDecisionRef]] = []
    for decision in store.decisions.values():
        if decision.id == exclude_id:
            continue
        if decision.status not in {"committed", "reviewed"}:
            continue
        blob = " ".join(
            part
            for part in (decision.question, decision.rationale or "", decision.outcome or "")
            if part
        )
        score = coverage(query, blob)
        if score < _MIN:
            continue
        chosen = next(
            (option.label for option in decision.options if option.id == decision.chosen_option_id),
            "",
        )
        ranked.append(
            (
                score,
                PriorDecisionRef(
                    decision_id=decision.id,
                    question=decision.question,
                    chosen_label=chosen,
                    outcome=decision.outcome,
                    status=decision.status,
                ),
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:limit]]
