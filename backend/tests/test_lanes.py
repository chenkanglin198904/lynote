from lynote.contracts.models import ChatRequest, CommitBriefRequest, CreateGoalRequest
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


def test_chat_and_commit_use_separate_lanes() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.lane == "learn"
    assert answer.goal_id == "goal_graph_vs_notes"
    users = [item for item in workspace.messages if item.role == "user"]
    assert users[-1].lane == "learn"
    brief = workspace.workbench().brief
    assert brief is not None
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=brief.options[0].id, rationale="先打穿筛选和主张层"),
    )
    decision_notes = [item for item in workspace.messages if item.lane == "decision"]
    assert len(decision_notes) == 1
    assert "决策" in decision_notes[0].content
    assert answer.lane == "learn"


def test_new_topic_starts_empty_learn_session() -> None:
    workspace = _workspace()
    workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    created = workspace.create_goal(CreateGoalRequest(title="大模型学习"))
    learn = [
        item
        for item in workspace.messages
        if item.lane == "learn" and item.goal_id == created.id
    ]
    assert learn == []
    leftover = [
        item
        for item in workspace.messages
        if item.lane == "learn" and item.goal_id == "goal_graph_vs_notes"
    ]
    assert leftover
