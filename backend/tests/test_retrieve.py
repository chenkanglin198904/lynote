from lynote.contracts.models import ChatRequest
from lynote.modules.retrieve.lexical import coverage
from lynote.providers.embeddings import HashingEmbedder
from lynote.providers.vectors import InMemoryVectorStore
from lynote.modules.retrieve.service import RetrieveService
from lynote.workspace import Workspace


def test_lexical_overlap_chinese() -> None:
    assert coverage("先全量入库再清理", "先把材料全收进向量库，以后再清理") > 0.1
    assert coverage("今晚吃什么", "没有筛选的图谱会变成垃圾场") < 0.05


def test_retrieve_hits_conflict_pair() -> None:
    workspace = Workspace(
        retrieve=RetrieveService(
            embedder=HashingEmbedder(dim=64),
            vectors=InMemoryVectorStore(),
            min_score=0.08,
        )
    )
    subgraph = workspace.retrieve.retrieve("先全量入库再清理行不行？", workspace.graph)
    claim_ids = {node.id for node in subgraph.nodes if node.kind == "claim"}
    assert "claim_ingest_all" in claim_ids
    assert "claim_rot" in claim_ids
    source_ids = {node.id for node in subgraph.nodes if node.kind == "source"}
    assert "src_filter_essay" in source_ids or "src_listicle" in source_ids


def test_retrieve_unknown_query_is_empty() -> None:
    workspace = Workspace(
        retrieve=RetrieveService(
            embedder=HashingEmbedder(dim=64),
            vectors=InMemoryVectorStore(),
        )
    )
    subgraph = workspace.retrieve.retrieve("今晚月球菜单有什么汤", workspace.graph)
    assert subgraph.nodes == []
    assert subgraph.edges == []
    answer = workspace.chat(ChatRequest(content="今晚月球菜单有什么汤"))
    assert answer.unknowns
    assert answer.claim_ids == []


def test_retrieve_pin_includes_node() -> None:
    workspace = Workspace(
        retrieve=RetrieveService(
            embedder=HashingEmbedder(dim=64),
            vectors=InMemoryVectorStore(),
        )
    )
    subgraph = workspace.retrieve.retrieve(
        "无关问题xyz",
        workspace.graph,
        pinned_node_ids=["claim_no_swarm"],
    )
    ids = {node.id for node in subgraph.nodes}
    assert "claim_no_swarm" in ids
    assert "src_mirosim" in ids
