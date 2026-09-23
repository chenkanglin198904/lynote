from lynote.contracts.models import (
    CommitBriefRequest,
    ComposeBriefRequest,
    CreateGoalRequest,
    IngestSourceRequest,
    ReviewBriefRequest,
)
from lynote.workspace import Workspace


def test_seed_graph_has_evidence_and_conflict() -> None:
    workspace = Workspace()
    assert workspace.graph.conflicts()
    for claim in workspace.graph.claims.values():
        assert claim.evidence, claim.id
    brief = workspace.workbench().brief
    assert brief is not None
    assert brief.skeptic


def test_gate_rejects_listicle() -> None:
    workspace = Workspace()
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="note",
            title="十大 AI 笔记神器，收藏即学会",
            text="盘点今年必看的十大 AI 笔记神器，一键导入全集，收藏即学会。",
        )
    )
    assert item.verdict == "reject"
    assert item.status == "pending"


def test_on_topic_note_can_pass_gate() -> None:
    workspace = Workspace()
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="note",
            title="主张层比文件夹更重要",
            text="笔记必须变成可召回的主张。没有证据的节点不要进入已确认层。个人知识图谱应该拒绝营销稿。",
        )
    )
    assert item.verdict in {"accept", "review"}


def test_accept_extracts_claims_with_evidence() -> None:
    workspace = Workspace()
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="note",
            title="主张层比文件夹更重要",
            text="笔记必须变成可召回的主张。没有证据的节点不要进入已确认层。",
        )
    )
    accepted = workspace.accept_inbox(item.id)
    assert accepted.status == "accepted"
    new_claims = [
        claim
        for claim in workspace.graph.claims.values()
        if any(evidence.source_id == item.source_id for evidence in claim.evidence)
    ]
    assert new_claims
    assert all(claim.evidence for claim in new_claims)


def test_commit_writes_decision() -> None:
    workspace = Workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    assert brief.options
    option_id = brief.options[0].id
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=option_id, rationale="先打穿筛选和主张层"),
    )
    decision = workspace.graph.decisions[brief.decision_id]
    assert decision.status == "committed"
    assert decision.chosen_option_id == option_id
    assert decision.rationale == "先打穿筛选和主张层"


def test_commit_rejects_empty_rationale() -> None:
    workspace = Workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    try:
        workspace.commit_brief(brief.id, CommitBriefRequest(option_id=brief.options[0].id, rationale="  "))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "理由" in str(exc)
    assert workspace.graph.decisions[brief.decision_id].status == "draft"


def test_create_goal_pauses_previous() -> None:
    workspace = Workspace()
    previous = next(goal for goal in workspace.graph.goals.values() if goal.status == "active")
    created = workspace.create_goal(
        CreateGoalRequest(title="本周判断", question="要不要先拒绝清单体再入库？")
    )
    assert created.status == "active"
    assert workspace.graph.goals[previous.id].status == "paused"
    assert workspace.graph.goals[created.id].question == "要不要先拒绝清单体再入库？"


def test_new_topic_hides_sample_graph() -> None:
    workspace = Workspace()
    seed_claims = set(workspace.graph.claims)
    created = workspace.create_goal(CreateGoalRequest(title="大模型学习"))
    view = workspace.workbench()
    node_ids = {node.id for node in view.graph.nodes}
    assert created.id in node_ids
    assert seed_claims.isdisjoint(node_ids)
    assert all(item.source_id in node_ids for item in view.inbox)
    if view.brief is not None:
        cited = {cid for option in view.brief.options for cid in option.supporting_claim_ids}
        assert seed_claims.isdisjoint(cited)


def test_activate_goal_restores_sample_topic() -> None:
    workspace = Workspace()
    sample = next(goal for goal in workspace.graph.goals.values() if goal.status == "active")
    workspace.create_goal(CreateGoalRequest(title="大模型学习"))
    workspace.activate_goal(sample.id)
    assert workspace.graph.goals[sample.id].status == "active"
    node_ids = {node.id for node in workspace.workbench().graph.nodes}
    assert "claim_rot" in node_ids
    assert workspace.brief is not None
    assert sample.question in workspace.brief.question or workspace.brief.question == sample.question


def test_review_writes_outcome() -> None:
    workspace = Workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    option_id = brief.options[0].id
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=option_id, rationale="先打穿筛选和主张层"),
    )
    reviewed = workspace.review_brief(
        brief.id,
        ReviewBriefRequest(outcome="筛选纪律守住了，笔记堆没有复发。"),
    )
    decision = workspace.graph.decisions[brief.decision_id]
    assert decision.status == "reviewed"
    assert decision.outcome == "筛选纪律守住了，笔记堆没有复发。"
    assert reviewed.outcome == decision.outcome
    assert reviewed.chosen_option_id == option_id
    view = workspace.workbench().brief
    assert view is not None
    assert view.outcome == decision.outcome


def test_review_rejects_draft() -> None:
    workspace = Workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    try:
        workspace.review_brief(brief.id, ReviewBriefRequest(outcome="还没拍板"))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "已采纳" in str(exc)
    assert workspace.graph.decisions[brief.decision_id].status == "draft"
    assert workspace.graph.decisions[brief.decision_id].outcome is None


def test_review_rejects_empty_outcome() -> None:
    workspace = Workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=brief.options[0].id, rationale="先打穿筛选和主张层"),
    )
    try:
        workspace.review_brief(brief.id, ReviewBriefRequest(outcome="  \n"))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "空" in str(exc)
    assert workspace.graph.decisions[brief.decision_id].status == "committed"


def test_compose_after_review_keeps_old_outcome() -> None:
    workspace = Workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    old_id = brief.decision_id
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=brief.options[0].id, rationale="先打穿筛选和主张层"),
    )
    workspace.review_brief(brief.id, ReviewBriefRequest(outcome="旧决策的结果"))
    next_brief = workspace.compose_brief(ComposeBriefRequest())
    assert next_brief.decision_id != old_id
    assert workspace.graph.decisions[old_id].status == "reviewed"
    assert workspace.graph.decisions[old_id].outcome == "旧决策的结果"
    assert workspace.graph.decisions[next_brief.decision_id].status == "draft"
    assert next_brief.outcome is None
