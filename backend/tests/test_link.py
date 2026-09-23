import pytest

from lynote.contracts.models import (
    ChatRequest,
    Claim,
    Evidence,
    LinkRelationRequest,
    Relation,
    Source,
    SourceSpan,
)
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


def _orphan_claim(workspace: Workspace) -> Claim:
    text = "间隔重复必须挂在已确认主张上才能出巩固题。"
    source = Source(
        id="src_orphan_span",
        kind="note",
        title="孤立主张材料",
        text=text,
        created_at="2026-09-17T00:00:00+00:00",
    )
    claim = Claim(
        id="claim_orphan_span",
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
    )
    workspace.graph.upsert_source(source)
    workspace.graph.upsert_claim(claim)
    workspace.graph.upsert_relation(
        Relation(
            id="rel_orphan_goal",
            from_id=claim.id,
            to_id="goal_graph_vs_notes",
            type="about",
        )
    )
    workspace.retrieve.sync(workspace.graph)
    return claim


def test_unlinked_answer_offers_existing_nodes_only() -> None:
    workspace = _workspace()
    claim = _orphan_claim(workspace)
    answer = workspace.chat(
        ChatRequest(content=claim.text, pinned_node_ids=[claim.id])
    )
    assert answer.grounded is not None
    assert answer.grounded.direct
    assert answer.grounded.unlinked is True
    assert answer.grounded.related == []
    assert answer.grounded.link_candidates
    known = set(workspace.graph.claims) | set(workspace.graph.concepts)
    for item in answer.grounded.link_candidates:
        assert item.from_id in known
        assert item.to_id in known
        assert item.from_id != "missing_node"
        assert item.to_id != "missing_node"


def test_confirm_related_writes_edge_and_refreshes_message() -> None:
    workspace = _workspace()
    claim = _orphan_claim(workspace)
    answer = workspace.chat(
        ChatRequest(content=claim.text, pinned_node_ids=[claim.id])
    )
    assert answer.grounded is not None
    candidate = answer.grounded.link_candidates[0]
    relation = workspace.link_related(
        LinkRelationRequest(
            from_id=candidate.from_id,
            to_id=candidate.to_id,
            message_id=answer.id,
        )
    )
    assert relation.type == "related_to"
    assert {relation.from_id, relation.to_id} == {candidate.from_id, candidate.to_id}
    stored = [
        item
        for item in workspace.graph.relations.values()
        if item.type == "related_to"
        and {item.from_id, item.to_id} == {candidate.from_id, candidate.to_id}
    ]
    assert stored
    saved = next(message for message in workspace.messages if message.id == answer.id)
    assert saved.grounded is not None
    assert saved.grounded.unlinked is False
    assert saved.grounded.link_candidates == []
    assert any(ref.id == candidate.to_id for ref in saved.grounded.related)
    again = workspace.link_related(
        LinkRelationRequest(from_id=candidate.from_id, to_id=candidate.to_id)
    )
    assert again.id == relation.id


def test_link_rejects_invented_and_source_nodes() -> None:
    workspace = _workspace()
    with pytest.raises(KeyError):
        workspace.link_related(
            LinkRelationRequest(from_id="claim_rot", to_id="claim_does_not_exist")
        )
    with pytest.raises(ValueError):
        workspace.link_related(
            LinkRelationRequest(from_id="claim_rot", to_id="src_filter_essay")
        )


def test_unknown_chat_has_no_link_candidates() -> None:
    answer = _workspace().chat(ChatRequest(content="今晚月球菜单有什么汤"))
    assert answer.grounded is not None
    assert answer.grounded.direct == []
    assert answer.grounded.unlinked is False
    assert answer.grounded.link_candidates == []
