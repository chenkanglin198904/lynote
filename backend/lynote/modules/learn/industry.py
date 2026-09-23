"""Industry-informed hang ranking. Search is a hint, not a taxonomy.

Code maps snippets onto existing concept/goal ids. Does not create nodes,
does not write claims, and does not ingest search pages.
"""

from __future__ import annotations

from lynote.contracts.models import Goal, HangCandidate, HangProposal, IndustryHint, Profile
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.modules.retrieve.lexical import coverage
from lynote.providers.websearch import SearchFn, search_web

_MIN = 0.18


def apply_industry_hints(
    store: InMemoryGraphStore,
    proposal: HangProposal,
    *,
    goal: Goal | None = None,
    profile: Profile | None = None,
    search: SearchFn | None = None,
) -> HangProposal:
    claims = [store.claims[cid] for cid in proposal.claim_ids if cid in store.claims]
    if not claims:
        return proposal
    domains = list(profile.domains) if profile else []
    known = _existing_targets(store, goal)
    if not known:
        return proposal
    query = _query(claims, goal, domains)
    hits = search_web(query, 4, search=search) if query else []
    by_id = {item.node_id: item for item in proposal.candidates}
    hints: list[IndustryHint] = []
    for hit in hits:
        text = f"{hit.title} {hit.snippet}"
        best_id, best_score = _best_existing(known, text)
        if best_id and best_score >= _MIN:
            _boost(by_id, store, known, best_id, best_score, hit.title)
            hints.append(
                IndustryHint(
                    title=hit.title,
                    url=hit.url,
                    snippet=hit.snippet,
                    matched_node_id=best_id,
                    matched_label=known[best_id][0],
                    reason="行业检索片段与已有概念/主题重叠，仅供归类，未入库",
                )
            )
        else:
            hints.append(
                IndustryHint(
                    title=hit.title,
                    url=hit.url,
                    snippet=hit.snippet,
                    reason="行业检索未对上图上已有节点，不能据此发明分类",
                )
            )
    for domain in domains[:4]:
        if not domain.strip():
            continue
        best_id, best_score = _best_existing(known, domain)
        if best_id and best_score >= _MIN:
            _boost(by_id, store, known, best_id, best_score, f"偏好领域「{domain}」")
    ranked = sorted(by_id.values(), key=lambda item: (item.kind != "goal", -item.score, item.label))
    goal_first: list[HangCandidate] = []
    rest: list[HangCandidate] = []
    for item in ranked:
        if item.kind == "goal":
            goal_first.append(item)
        else:
            rest.append(item)
    return proposal.model_copy(
        update={
            "candidates": goal_first + rest[:6],
            "industry_hints": hints[:4],
        }
    )


def _existing_targets(
    store: InMemoryGraphStore, goal: Goal | None
) -> dict[str, tuple[str, str]]:
    known: dict[str, tuple[str, str]] = {}
    for concept in store.concepts.values():
        label = " ".join(part for part in (concept.name, *concept.aliases, concept.definition or "") if part)
        known[concept.id] = (concept.name, label)
    if goal is not None and goal.id in store.goals:
        known[goal.id] = (goal.title, f"{goal.title} {goal.question}")
    return known


def _best_existing(
    known: dict[str, tuple[str, str]], blob: str
) -> tuple[str, float]:
    best_id = ""
    best = 0.0
    for node_id, (name, label) in known.items():
        score = max(coverage(name, blob), coverage(blob, label), coverage(label, blob))
        if score > best:
            best = score
            best_id = node_id
    return best_id, best


def _boost(
    by_id: dict[str, HangCandidate],
    store: InMemoryGraphStore,
    known: dict[str, tuple[str, str]],
    node_id: str,
    score: float,
    why: str,
) -> None:
    current = by_id.get(node_id)
    kind: str = "goal" if node_id in store.goals else "concept"
    label = known[node_id][0]
    reason = f"行业综合判断：{why}"[:80]
    if current is None:
        by_id[node_id] = HangCandidate(
            node_id=node_id,
            kind=kind,  # type: ignore[arg-type]
            label=label,
            score=round(min(1.0, 0.4 + score), 3),
            reason=reason,
        )
        return
    by_id[node_id] = current.model_copy(
        update={
            "score": round(min(1.0, current.score + 0.2 + 0.3 * score), 3),
            "reason": reason if "行业" not in current.reason else current.reason,
        }
    )


def _query(claims, goal: Goal | None, domains: list[str]) -> str:
    parts: list[str] = []
    if goal is not None:
        parts.append(goal.title)
    parts.extend(item.strip() for item in domains[:2] if item.strip())
    text = " ".join(claim.text for claim in claims)
    compact = "".join(text.split())
    if compact:
        parts.append(compact[:48])
    return " ".join(parts).strip()[:120]
