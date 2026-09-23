"""Graph module. Storage only — no LLM."""

from lynote.modules.graph.factory import build_graph_store
from lynote.modules.graph.store import InMemoryGraphStore

__all__ = ["InMemoryGraphStore", "build_graph_store"]
