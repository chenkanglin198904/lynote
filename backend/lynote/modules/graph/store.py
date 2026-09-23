"""Graph store: CRUD + conflict queries. Must not call an LLM."""

from __future__ import annotations

from lynote.contracts.models import (
    Claim,
    Concept,
    Decision,
    Goal,
    GraphNode,
    GraphSnapshot,
    Misconception,
    Relation,
    Source,
)


class InMemoryGraphStore:
    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.concepts: dict[str, Concept] = {}
        self.claims: dict[str, Claim] = {}
        self.goals: dict[str, Goal] = {}
        self.decisions: dict[str, Decision] = {}
        self.misconceptions: dict[str, Misconception] = {}
        self.relations: dict[str, Relation] = {}

    def upsert_source(self, source: Source) -> Source:
        self.sources[source.id] = source
        return source

    def upsert_concept(self, concept: Concept) -> Concept:
        self.concepts[concept.id] = concept
        return concept

    def upsert_claim(self, claim: Claim) -> Claim:
        if not claim.evidence:
            raise ValueError("claim must carry evidence")
        if not any(item.source_span is not None for item in claim.evidence):
            raise ValueError("claim must carry source_span")
        self.claims[claim.id] = claim
        return claim

    def upsert_goal(self, goal: Goal) -> Goal:
        self.goals[goal.id] = goal
        return goal

    def upsert_decision(self, decision: Decision) -> Decision:
        self.decisions[decision.id] = decision
        return decision

    def upsert_misconception(self, item: Misconception) -> Misconception:
        if item.claim_id not in self.claims:
            raise ValueError("misconception must hang on an existing claim")
        self.misconceptions[item.id] = item
        return item

    def upsert_relation(self, relation: Relation) -> Relation:
        self.relations[relation.id] = relation
        return relation

    def close(self) -> None:
        return None

    def is_empty(self) -> bool:
        return not (
            self.sources
            or self.concepts
            or self.claims
            or self.goals
            or self.decisions
            or self.misconceptions
        )

    def active_goals(self) -> list[Goal]:
        return [g for g in self.goals.values() if g.status == "active"]

    def conflicts(self) -> list[tuple[Claim, Claim]]:
        pairs: list[tuple[Claim, Claim]] = []
        seen: set[tuple[str, str]] = set()
        for claim in self.claims.values():
            for other_id in claim.opposed_claim_ids:
                other = self.claims.get(other_id)
                if other is None:
                    continue
                key = tuple(sorted((claim.id, other.id)))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append((claim, other))
        for rel in self.relations.values():
            if rel.type != "contradicts":
                continue
            left = self.claims.get(rel.from_id)
            right = self.claims.get(rel.to_id)
            if left is None or right is None:
                continue
            key = tuple(sorted((left.id, right.id)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((left, right))
        return pairs

    def remove_relation(self, relation_id: str) -> None:
        self.relations.pop(relation_id, None)

    def remove_concept(self, concept_id: str) -> None:
        self.concepts.pop(concept_id, None)
        stale = [
            rel.id
            for rel in self.relations.values()
            if rel.from_id == concept_id or rel.to_id == concept_id
        ]
        for rel_id in stale:
            self.relations.pop(rel_id, None)

    def as_node(self, node_id: str) -> GraphNode | None:
        source = self.sources.get(node_id)
        if source is not None:
            return GraphNode(id=source.id, kind="source", label=source.title, subtitle=source.kind)
        concept = self.concepts.get(node_id)
        if concept is not None:
            return GraphNode(id=concept.id, kind="concept", label=concept.name, subtitle=concept.domain)
        claim = self.claims.get(node_id)
        if claim is not None:
            return GraphNode(
                id=claim.id,
                kind="claim",
                label=claim.text,
                subtitle=claim.status,
                status=claim.status,
            )
        goal = self.goals.get(node_id)
        if goal is not None:
            return GraphNode(
                id=goal.id,
                kind="goal",
                label=goal.title,
                subtitle=goal.status,
                status=goal.status,
            )
        decision = self.decisions.get(node_id)
        if decision is not None:
            return GraphNode(
                id=decision.id,
                kind="decision",
                label=decision.question,
                subtitle=decision.status,
                status=decision.status,
            )
        item = self.misconceptions.get(node_id)
        if item is not None:
            return GraphNode(
                id=item.id,
                kind="misconception",
                label=item.text,
                subtitle=item.status,
                status=item.status,
            )
        return None

    def snapshot(self) -> GraphSnapshot:
        return self._snapshot_ids(None)

    def neighborhood(self, root_id: str, hops: int | None = None) -> GraphSnapshot:
        if self.as_node(root_id) is None:
            return GraphSnapshot(nodes=[], edges=[])
        adjacent: dict[str, set[str]] = {}
        for rel in self.relations.values():
            adjacent.setdefault(rel.from_id, set()).add(rel.to_id)
            adjacent.setdefault(rel.to_id, set()).add(rel.from_id)
        seen = {root_id}
        frontier = {root_id}
        hop = 0
        while frontier:
            if hops is not None and hop >= hops:
                break
            hop += 1
            nxt: set[str] = set()
            for node_id in frontier:
                for neighbor in adjacent.get(node_id, ()):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        nxt.add(neighbor)
            frontier = nxt
        return self._snapshot_ids(seen)

    def _snapshot_ids(self, allowed: set[str] | None) -> GraphSnapshot:
        nodes: list[GraphNode] = []
        for source in self.sources.values():
            if allowed is None or source.id in allowed:
                nodes.append(
                    GraphNode(
                        id=source.id,
                        kind="source",
                        label=source.title,
                        subtitle=source.kind,
                    )
                )
        for concept in self.concepts.values():
            if allowed is None or concept.id in allowed:
                nodes.append(
                    GraphNode(
                        id=concept.id,
                        kind="concept",
                        label=concept.name,
                        subtitle=concept.domain,
                    )
                )
        for claim in self.claims.values():
            if allowed is None or claim.id in allowed:
                nodes.append(
                    GraphNode(
                        id=claim.id,
                        kind="claim",
                        label=claim.text,
                        subtitle=claim.status,
                        status=claim.status,
                    )
                )
        for goal in self.goals.values():
            if allowed is None or goal.id in allowed:
                nodes.append(
                    GraphNode(
                        id=goal.id,
                        kind="goal",
                        label=goal.title,
                        subtitle=goal.status,
                        status=goal.status,
                    )
                )
        for decision in self.decisions.values():
            if allowed is None or decision.id in allowed:
                nodes.append(
                    GraphNode(
                        id=decision.id,
                        kind="decision",
                        label=decision.question,
                        subtitle=decision.status,
                        status=decision.status,
                    )
                )
        for item in self.misconceptions.values():
            if allowed is None or item.id in allowed:
                nodes.append(
                    GraphNode(
                        id=item.id,
                        kind="misconception",
                        label=item.text,
                        subtitle=item.status,
                        status=item.status,
                    )
                )
        edges = [
            rel
            for rel in self.relations.values()
            if allowed is None or (rel.from_id in allowed and rel.to_id in allowed)
        ]
        return GraphSnapshot(nodes=nodes, edges=edges)
