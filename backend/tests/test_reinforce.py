import pytest

from lynote.contracts.models import CaptureLessonRequest, ChatRequest, CommitBriefRequest, PracticeStat
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


def test_touch_schedules_review_and_boosts_retrieve() -> None:
    from lynote.modules.retrieve.service import _use_boost

    workspace = _workspace()
    query = "个人决策要不要模拟社会"
    before = dict(workspace.retrieve._rank_claims(query, workspace.graph, None))
    saved = workspace.touch_claim("claim_no_swarm")
    assert saved["use_count"] == 1
    stat = workspace.practice["goal_graph_vs_notes:claim_no_swarm"]
    assert stat.use_count == 1
    assert stat.next_review_at
    assert _use_boost(workspace.practice, "claim_no_swarm") == pytest.approx(0.06)
    learn = workspace.workbench().learn
    assert learn is not None
    review = next(item for item in learn.reviews if item.claim_id == "claim_no_swarm")
    assert "用过" in review.reason
    today = workspace.workbench().today
    card = next(item for item in today.reviews if item.id == "claim_no_swarm")
    assert "用过" in card.detail
    after = dict(
        workspace.retrieve._rank_claims(
            query,
            workspace.graph,
            None,
            practice=workspace.practice,
        )
    )
    assert after["claim_no_swarm"] > before["claim_no_swarm"]


def test_touch_coalesces_repeats() -> None:
    workspace = _workspace()
    workspace.touch_claim("claim_evidence")
    workspace.touch_claim("claim_evidence")
    assert workspace.practice["goal_graph_vs_notes:claim_evidence"].use_count == 1


def test_capture_and_hang_record_use() -> None:
    workspace = _workspace()
    answer = workspace.chat(
        ChatRequest(
            content="主张必须挂证据才能进入已确认层。",
            pinned_node_ids=["claim_evidence"],
        )
    )
    workspace.capture_lesson(
        CaptureLessonRequest(message_id=answer.id, chapter_id="concept_pkg")
    )
    stat = workspace.practice["goal_graph_vs_notes:claim_evidence"]
    assert stat.use_count >= 1


def test_commit_brief_records_supporting_claims() -> None:
    workspace = _workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    option = next(item for item in brief.options if "claim_rot" in item.supporting_claim_ids)
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=option.id, rationale="要对上出处，不能全收进库。"),
    )
    stat = workspace.practice["goal_graph_vs_notes:claim_rot"]
    assert stat.use_count >= 1


def test_cannot_touch_missing_claim() -> None:
    workspace = _workspace()
    with pytest.raises(KeyError):
        workspace.touch_claim("claim_does_not_exist")


def test_future_review_stays_off_today() -> None:
    workspace = _workspace()
    workspace.practice["goal_graph_vs_notes:claim_evidence"] = PracticeStat(
        goal_id="goal_graph_vs_notes",
        claim_id="claim_evidence",
        use_count=3,
        next_review_at="2099-01-01T00:00:00+00:00",
    )
    learn = workspace.workbench().learn
    assert learn is not None
    assert all(item.claim_id != "claim_evidence" for item in learn.reviews)


def test_use_does_not_pad_unknown_query() -> None:
    workspace = _workspace()
    workspace.touch_claim("claim_rot")
    subgraph = workspace.retrieve.retrieve(
        "今晚月球菜单有什么汤",
        workspace.graph,
        practice=workspace.practice,
    )
    assert subgraph.nodes == []
