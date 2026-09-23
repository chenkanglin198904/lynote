"""Graph store factory. memory for tests, kuzu for the running app."""

from __future__ import annotations

from pathlib import Path

from lynote.config import settings
from lynote.modules.graph.store import InMemoryGraphStore


def build_graph_store(path: str | Path | None = None) -> InMemoryGraphStore:
    backend = settings.graph_backend.strip().lower()
    if backend in {"", "memory"}:
        return InMemoryGraphStore()
    from lynote.modules.graph.kuzu_store import KuzuGraphStore

    return KuzuGraphStore(path or settings.resolve_data_path(settings.graph_path))
