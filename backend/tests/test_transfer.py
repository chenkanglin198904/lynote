from lynote.contracts.models import ChatRequest, Claim, Evidence, Relation, Source, SourceSpan
from lynote.modules.tutor.transfer import find_transfers
from lynote.providers.embeddings import HashingEmbedder
from lynote.providers.vectors import InMemoryVectorStore
from lynote.modules.retrieve.service import RetrieveService
from lynote.workspace import Workspace


def _workspace() -> Workspace:
    return Workspace(
        retrieve=RetrieveService(
            embedder=HashingEmbedder(dim=64),
            vectors=InMemoryVectorStore(),
            min_score=0.08,
        )
    )


def _add_graphrag_tradeoff(workspace: Workspace) -> Claim:
    text = "用图约束检索也不能跳过拒绝率。"
    source = Source(
        id="src_graphrag_gate",
        kind="markdown",
        title="检索图同样要拒绝",
        text=text,
        created_at="2026-09-18T00:00:00+00:00",
    )
    claim = Claim(
        id="claim_graphrag_gate",
        text=text.rstrip("。"),
        polarity="asserts",
        confidence=0.8,
        status="confirmed",
        evidence=[
            Evidence(
                source_id=source.id,
                quote=text,
                source_span=SourceSpan(start=0, end=len(text)),
            )
        ],
        opposed_claim_ids=["claim_ingest_all"],
    )
    workspace.graph.upsert_source(source)
    workspace.graph.upsert_claim(claim)
    workspace.graph.upsert_relation(
        Relation(id="rel_graphrag_about", from_id=claim.id, to_id="concept_graphrag", type="about")
    )
    workspace.graph.upsert_relation(
        Relation(id="rel_graphrag_vs_all", from_id=claim.id, to_id="claim_ingest_all", type="contradicts")
    )
    workspace.graph.upsert_relation(
        Relation(id="rel_graphrag_goal", from_id=claim.id, to_id="goal_graph_vs_notes", type="about")
    )
    workspace.retrieve.sync(workspace.graph)
    return claim


def test_seed_has_no_invented_transfer() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会变成垃圾场"))
    assert answer.grounded is not None
    assert answer.grounded.transfers == []
    assert "同一类取舍" not in answer.content


def test_transfer_follows_related_concept_edge() -> None:
    workspace = _workspace()
    analog = _add_graphrag_tradeoff(workspace)
    found = find_transfers([workspace.graph.claims["claim_rot"]], workspace.graph)
    assert any(item.to_id == analog.id for item in found)
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会变成垃圾场"))
    assert answer.grounded is not None
    assert any(item.to_id == analog.id for item in answer.grounded.transfers)
    assert analog.id in answer.claim_ids
    assert "同一类取舍" in answer.content
    assert analog.text in answer.content


def test_no_edge_does_not_invent_transfer() -> None:
    workspace = _workspace()
    analog = _add_graphrag_tradeoff(workspace)
    drop = [
        key
        for key, rel in workspace.graph.relations.items()
        if rel.type == "related_to"
        and {rel.from_id, rel.to_id} == {"concept_graphrag", "concept_pkg"}
    ]
    for key in drop:
        del workspace.graph.relations[key]
    found = find_transfers([workspace.graph.claims["claim_rot"]], workspace.graph)
    assert all(item.to_id != analog.id for item in found)
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会变成垃圾场"))
    assert answer.grounded is not None
    assert all(item.to_id != analog.id for item in answer.grounded.transfers)
    assert "同一类取舍" not in answer.content
    assert any(item.to_id == analog.id for item in answer.grounded.link_candidates)
