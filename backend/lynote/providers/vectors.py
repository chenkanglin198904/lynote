"""Vector stores. LanceDB is the default on-disk backend; tests force memory."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lynote.config import settings


@dataclass(frozen=True)
class VectorHit:
    id: str
    score: float


class VectorStore(Protocol):
    name: str

    def upsert(self, items: list[tuple[str, list[float]]]) -> None: ...

    def search(self, query: list[float], top_k: int) -> list[VectorHit]: ...


class InMemoryVectorStore:
    name = "memory"

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}

    def upsert(self, items: list[tuple[str, list[float]]]) -> None:
        for item_id, vector in items:
            self._vectors[item_id] = vector

    def search(self, query: list[float], top_k: int) -> list[VectorHit]:
        scored = [
            VectorHit(id=item_id, score=_cosine(query, vector))
            for item_id, vector in self._vectors.items()
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return [item for item in scored if item.score > 0][:top_k]


class LanceDbVectorStore:
    """On-disk vectors. Restart must still find the same claim ids."""

    name = "lancedb"

    def __init__(self, path: str | Path | None = None) -> None:
        try:
            import lancedb  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "VECTOR_BACKEND=lancedb needs lancedb: pip install 'lynote[vectors]'"
            ) from exc
        raw = Path(path) if path is not None else Path(settings.vector_path)
        if not raw.is_absolute():
            raw = settings.resolve_data_path(str(raw))
        raw.mkdir(parents=True, exist_ok=True)
        self.path = raw
        self._db = lancedb.connect(str(raw))
        self._table_name = "claims"
        self._table = None
        names = self._db.table_names()
        if self._table_name in names:
            self._table = self._db.open_table(self._table_name)

    def upsert(self, items: list[tuple[str, list[float]]]) -> None:
        if not items:
            return
        rows = [{"id": item_id, "vector": vector} for item_id, vector in items]
        if self._table is None:
            names = self._db.table_names()
            if self._table_name in names:
                self._table = self._db.open_table(self._table_name)
            else:
                self._table = self._db.create_table(self._table_name, rows, mode="overwrite")
                return
        ids = [row["id"] for row in rows]
        clause = " OR ".join(f"id = '{_sql_escape(item_id)}'" for item_id in ids)
        try:
            self._table.delete(clause)
        except Exception:
            pass
        self._table.add(rows)

    def search(self, query: list[float], top_k: int) -> list[VectorHit]:
        if self._table is None:
            names = self._db.table_names()
            if self._table_name not in names:
                return []
            self._table = self._db.open_table(self._table_name)
        rows = self._table.search(query).limit(top_k).to_list()
        hits: list[VectorHit] = []
        for row in rows:
            distance = float(row.get("_distance", 0.0))
            score = 1.0 / (1.0 + max(distance, 0.0))
            hits.append(VectorHit(id=str(row["id"]), score=score))
        return hits


def build_vector_store() -> VectorStore:
    backend = settings.vector_backend.strip().lower()
    if backend in {"", "memory"}:
        return InMemoryVectorStore()
    if backend == "lancedb":
        return LanceDbVectorStore()
    return InMemoryVectorStore()


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def _cosine(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    dot = sum(left[i] * right[i] for i in range(size))
    norm_l = math.sqrt(sum(left[i] * left[i] for i in range(size)))
    norm_r = math.sqrt(sum(right[i] * right[i] for i in range(size)))
    if norm_l == 0 or norm_r == 0:
        return 0.0
    return dot / (norm_l * norm_r)
