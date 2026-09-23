import pytest

from lynote.contracts.models import CaptureLessonRequest, ChatMessage, ChatRequest, Claim, Evidence, SourceSpan
from lynote.modules.learn.outline import capture_to_chapter, compose_outline
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


def test_outline_uses_existing_concepts_only() -> None:
    workspace = _workspace()
    outline = workspace.workbench().outline
    assert outline is not None
    titles = [item.title for item in outline.chapters]
    assert titles == sorted(titles)
    assert "个人知识图谱" in titles
    assert "笔记堆积" in titles
    assert "GraphRAG" not in titles
    known = {item.name for item in workspace.graph.concepts.values()}
    known.update(goal.title for goal in workspace.graph.goals.values())
    known.update(claim.text for claim in workspace.graph.claims.values())
    for chapter in [*outline.chapters, *outline.loose_claims]:
        assert chapter.title in known
        assert all(claim_id in workspace.graph.claims for claim_id in chapter.claim_ids)
    assert "不另编教材大纲" in outline.intro
    assert outline.goal_id == "goal_graph_vs_notes"


def test_outline_without_goal_does_not_invent_chapters() -> None:
    workspace = _workspace()
    outline = compose_outline(workspace.graph, None)
    assert outline.chapters == []
    assert outline.loose_claims == []
    assert "先建" in outline.intro


def test_capture_attaches_cited_claims_and_rejects_invented_nodes() -> None:
    workspace = _workspace()
    answer = workspace.chat(
        ChatRequest(
            content="主张必须挂证据才能进入已确认层。",
            pinned_node_ids=["claim_evidence"],
        )
    )
    assert answer.grounded is not None
    cited = [ref.id for ref in answer.grounded.direct if ref.kind == "claim"]
    assert "claim_evidence" in cited
    assert all(claim_id in workspace.graph.claims for claim_id in cited)
    written = workspace.capture_lesson(
        CaptureLessonRequest(message_id=answer.id, chapter_id="concept_pkg")
    )
    assert written
    assert all(rel.type == "about" and rel.to_id == "concept_pkg" for rel in written)
    assert all(rel.from_id in workspace.graph.claims for rel in written)
    chapter = next(item for item in workspace.workbench().outline.chapters if item.id == "concept_pkg")
    assert "claim_evidence" in chapter.claim_ids

    with pytest.raises(ValueError, match="没有可收入"):
        workspace.capture_lesson(
            CaptureLessonRequest(message_id=answer.id, chapter_id="concept_pkg")
        )
    with pytest.raises(KeyError):
        workspace.capture_lesson(
            CaptureLessonRequest(message_id=answer.id, chapter_id="concept_invented")
        )
    with pytest.raises(ValueError, match="不能发明节点"):
        workspace.capture_lesson(
            CaptureLessonRequest(message_id=answer.id, chapter_id="claim_rot")
        )


def test_capture_empty_message_does_not_mint_claims() -> None:
    workspace = _workspace()
    workspace.messages.append(
        ChatMessage(id="msg_empty_capture", role="assistant", content="没有引用", claim_ids=[])
    )
    before = len(workspace.graph.claims)
    with pytest.raises(ValueError, match="没有可收入"):
        workspace.capture_lesson(
            CaptureLessonRequest(message_id="msg_empty_capture", chapter_id="concept_pkg")
        )
    assert len(workspace.graph.claims) == before
    with pytest.raises(ValueError, match="没有可收入"):
        capture_to_chapter(
            workspace.graph,
            chapter_id="concept_pkg",
            claim_ids=["claim_does_not_exist"],
        )
    fake = Claim(
        id="claim_unbound",
        text="这是一条没有挂到任何章节的测试主张",
        polarity="asserts",
        confidence=0.5,
        status="confirmed",
        evidence=[
            Evidence(
                source_id="src_filter_essay",
                quote="知识图谱质量由拒绝率决定。",
                source_span=SourceSpan(start=0, end=13),
            )
        ],
    )
    workspace.graph.upsert_claim(fake)
    written = capture_to_chapter(workspace.graph, chapter_id="goal_graph_vs_notes", claim_ids=[fake.id])
    assert written[0].from_id == fake.id
    assert written[0].to_id == "goal_graph_vs_notes"
    assert fake.id in workspace.graph.claims
