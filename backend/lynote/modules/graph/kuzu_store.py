"""Kuzu-backed graph store. Same in-memory read surface, writes go to disk."""

from __future__ import annotations

import json
from pathlib import Path

from lynote.contracts.models import Claim, Concept, Decision, Goal, Misconception, Relation, Source
from lynote.modules.graph.store import InMemoryGraphStore

_SCHEMA = """
CREATE NODE TABLE IF NOT EXISTS Entity(
    id STRING,
    kind STRING,
    payload STRING,
    PRIMARY KEY(id)
);
CREATE REL TABLE IF NOT EXISTS Link(
    FROM Entity TO Entity,
    rel_id STRING,
    type STRING,
    weight DOUBLE,
    source_id STRING
);
"""


class KuzuGraphStore(InMemoryGraphStore):
    def __init__(self, path: str | Path) -> None:
        super().__init__()
        try:
            import kuzu
        except ImportError as exc:
            raise RuntimeError("GRAPH_BACKEND=kuzu needs the kuzu package") from exc
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(self.path))
        self._conn = kuzu.Connection(self._db)
        self._ensure_schema()
        self._hydrate()

    def close(self) -> None:
        conn = getattr(self, "_conn", None)
        db = getattr(self, "_db", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._conn = None
        if db is not None:
            closer = getattr(db, "close", None)
            if closer is not None:
                try:
                    closer()
                except Exception:
                    pass
            self._db = None

    def upsert_source(self, source: Source) -> Source:
        super().upsert_source(source)
        self._write_entity("source", source.id, source.model_dump())
        return source

    def upsert_concept(self, concept: Concept) -> Concept:
        super().upsert_concept(concept)
        self._write_entity("concept", concept.id, concept.model_dump())
        return concept

    def upsert_claim(self, claim: Claim) -> Claim:
        super().upsert_claim(claim)
        self._write_entity("claim", claim.id, claim.model_dump())
        return claim

    def upsert_goal(self, goal: Goal) -> Goal:
        super().upsert_goal(goal)
        self._write_entity("goal", goal.id, goal.model_dump())
        return goal

    def upsert_decision(self, decision: Decision) -> Decision:
        super().upsert_decision(decision)
        self._write_entity("decision", decision.id, decision.model_dump())
        return decision

    def upsert_misconception(self, item: Misconception) -> Misconception:
        super().upsert_misconception(item)
        self._write_entity("misconception", item.id, item.model_dump())
        return item

    def upsert_relation(self, relation: Relation) -> Relation:
        super().upsert_relation(relation)
        if relation.from_id in self._entity_ids() and relation.to_id in self._entity_ids():
            self._write_link(relation)
        return relation

    def remove_relation(self, relation_id: str) -> None:
        super().remove_relation(relation_id)
        try:
            self._conn.execute(
                "MATCH ()-[r:Link]->() WHERE r.rel_id = $rid DELETE r",
                {"rid": relation_id},
            )
        except RuntimeError:
            pass

    def remove_concept(self, concept_id: str) -> None:
        touching = [
            rel.id
            for rel in self.relations.values()
            if rel.from_id == concept_id or rel.to_id == concept_id
        ]
        for rel_id in touching:
            self.remove_relation(rel_id)
        super().remove_concept(concept_id)
        try:
            self._conn.execute("MATCH (n:Entity {id: $id}) DELETE n", {"id": concept_id})
        except RuntimeError:
            pass

    def _entity_ids(self) -> set[str]:
        return (
            set(self.sources)
            | set(self.concepts)
            |             set(self.claims)
            | set(self.goals)
            | set(self.decisions)
            | set(self.misconceptions)
        )

    def _ensure_schema(self) -> None:
        for statement in _SCHEMA.strip().split(";"):
            sql = statement.strip()
            if not sql:
                continue
            try:
                self._conn.execute(sql)
            except RuntimeError as exc:
                if "already exists" not in str(exc).lower():
                    raise

    def _hydrate(self) -> None:
        nodes = _rows(
            self._conn.execute("MATCH (n:Entity) RETURN n.id, n.kind, n.payload")
        )
        for _node_id, kind, payload_raw in nodes:
            payload = json.loads(payload_raw)
            if kind == "source":
                source = Source.model_validate(payload)
                self.sources[source.id] = source
            elif kind == "concept":
                concept = Concept.model_validate(payload)
                self.concepts[concept.id] = concept
            elif kind == "claim":
                claim = Claim.model_validate(payload)
                self.claims[claim.id] = claim
            elif kind == "goal":
                goal = Goal.model_validate(payload)
                self.goals[goal.id] = goal
            elif kind == "decision":
                decision = Decision.model_validate(payload)
                self.decisions[decision.id] = decision
            elif kind == "misconception":
                item = Misconception.model_validate(payload)
                self.misconceptions[item.id] = item
        links = _rows(
            self._conn.execute(
                "MATCH (a:Entity)-[r:Link]->(b:Entity) "
                "RETURN r.rel_id, a.id, b.id, r.type, r.weight, r.source_id"
            )
        )
        for rel_id, from_id, to_id, rel_type, weight, source_id in links:
            relation = Relation(
                id=str(rel_id),
                from_id=str(from_id),
                to_id=str(to_id),
                type=rel_type,
                weight=None if weight is None else float(weight),
                source_id=source_id or None,
            )
            self.relations[relation.id] = relation

    def _write_entity(self, kind: str, entity_id: str, payload: dict) -> None:
        self._conn.execute(
            "MERGE (n:Entity {id: $id}) SET n.kind = $kind, n.payload = $payload",
            {
                "id": entity_id,
                "kind": kind,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )

    def _write_link(self, relation: Relation) -> None:
        try:
            self._conn.execute(
                "MATCH ()-[r:Link]->() WHERE r.rel_id = $rid DELETE r",
                {"rid": relation.id},
            )
        except RuntimeError:
            pass
        self._conn.execute(
            """
            MATCH (a:Entity {id: $from_id}), (b:Entity {id: $to_id})
            CREATE (a)-[:Link {
                rel_id: $rid,
                type: $type,
                weight: $weight,
                source_id: $source_id
            }]->(b)
            """,
            {
                "from_id": relation.from_id,
                "to_id": relation.to_id,
                "rid": relation.id,
                "type": relation.type,
                "weight": float(relation.weight or 0.0),
                "source_id": relation.source_id or "",
            },
        )


def _rows(result) -> list[list]:
    rows: list[list] = []
    while result.has_next():
        rows.append(result.get_next())
    result.close()
    return rows
