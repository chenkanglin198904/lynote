from pathlib import Path

from lynote.providers.embeddings import HashingEmbedder
from lynote.providers.vectors import InMemoryVectorStore, LanceDbVectorStore, build_vector_store
from lynote.modules.retrieve.service import RetrieveService
from lynote.workspace import Workspace


def test_lancedb_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "vectors"
    first = LanceDbVectorStore(path)
    first.upsert([("claim_rot", [1.0, 0.0, 0.0]), ("claim_other", [0.0, 1.0, 0.0])])
    second = LanceDbVectorStore(path)
    hits = second.search([1.0, 0.0, 0.0], 2)
    assert hits
    assert hits[0].id == "claim_rot"
    assert "claim_does_not_exist" not in {hit.id for hit in hits}


def test_workspace_sync_persists_vectors(tmp_path: Path) -> None:
    embedder = HashingEmbedder(dim=8)
    store = LanceDbVectorStore(tmp_path / "ws-vectors")
    workspace = Workspace(
        retrieve=RetrieveService(
            embedder=embedder,
            vectors=store,
            min_score=0.0,
        )
    )
    workspace.retrieve.sync(workspace.graph)
    from lynote.modules.retrieve.service import _claim_blob

    query = embedder.embed([_claim_blob(workspace.graph.claims["claim_rot"])])[0]
    restored = LanceDbVectorStore(tmp_path / "ws-vectors")
    hits = restored.search(query, 5)
    assert hits
    assert hits[0].id == "claim_rot"


def test_build_vector_store_tests_use_memory() -> None:
    assert build_vector_store().name == "memory"
    assert InMemoryVectorStore().name == "memory"
