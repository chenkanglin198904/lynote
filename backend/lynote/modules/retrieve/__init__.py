"""Retrieve module. Subgraph only — no prose generation."""

from lynote.modules.retrieve.search import search_knowledge
from lynote.modules.retrieve.service import RetrieveService

__all__ = ["RetrieveService", "search_knowledge"]
