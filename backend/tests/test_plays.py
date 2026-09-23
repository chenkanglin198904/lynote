from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from lynote.contracts.models import CommitBriefRequest, RunPlayRequest
from lynote.modules.learn.plays import catalog, get_play
from lynote.modules.retrieve.context import play_boost
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


def test_play_catalog_is_fixed_not_a_plugin_store() -> None:
    plays = catalog()
    assert [item.id for item in plays] == ["read_article", "after_meeting"]
    workspace = _workspace()
    assert [item.id for item in workspace.workbench().plays] == ["read_article", "after_meeting"]
    try:
        RunPlayRequest(play_id="install_skill")  # type: ignore[arg-type]
        raise AssertionError("unknown play should fail")
    except ValidationError:
        pass
    try:
        get_play("install_skill")
        raise AssertionError("unknown play should fail")
    except ValueError as exc:
        assert "插件" in str(exc)


def test_read_article_play_gates_without_extracting() -> None:
    workspace = _workspace()
    before_claims = set(workspace.graph.claims)
    before_concepts = set(workspace.graph.concepts)
    result = workspace.run_play(
        RunPlayRequest(
            play_id="read_article",
            kind="markdown",
            title="无筛选会腐烂",
            text="知识图谱质量由拒绝率决定。主张必须挂证据才能进入已确认层。互相打架的结论不要偷偷合并。",
        )
    )
    assert result.play.id == "read_article"
    assert result.inbox.status == "pending"
    assert result.inbox.id in workspace.inbox
    assert result.brief is None
    assert set(workspace.graph.claims) == before_claims
    assert set(workspace.graph.concepts) == before_concepts
    assert workspace.hangs == []
    assert "下一步" in result.next_hint
    try:
        workspace.run_play(
            RunPlayRequest(
                play_id="read_article",
                kind="note",
                text="这是一句足够长的随手记，用来走错剧本路径。",
            )
        )
        raise AssertionError("read_article must not take notes")
    except ValueError:
        pass
    try:
        workspace.run_play(
            RunPlayRequest(
                play_id="read_article",
                kind="markdown",
                text="知识图谱质量由拒绝率决定。主张必须挂证据。",
                compose_brief=True,
            )
        )
        raise AssertionError("read_article must not compose brief")
    except ValueError:
        pass


def test_after_meeting_play_can_open_brief_without_accepting() -> None:
    workspace = _workspace()
    before_claims = set(workspace.graph.claims)
    before_concepts = set(workspace.graph.concepts)
    result = workspace.run_play(
        RunPlayRequest(
            play_id="after_meeting",
            text="会上决定先打穿筛选，必须拒绝清单体，不要全量入库。",
            compose_brief=True,
        )
    )
    assert result.inbox.status == "pending"
    assert result.inbox.source_id in workspace.graph.sources
    assert workspace.graph.sources[result.inbox.source_id].kind == "note"
    assert result.brief is not None
    assert workspace.brief_touched_at is not None
    assert set(workspace.graph.claims) == before_claims
    assert set(workspace.graph.concepts) == before_concepts
    assert "简报" in result.next_hint
    try:
        workspace.run_play(
            RunPlayRequest(
                play_id="after_meeting",
                kind="url",
                uri="https://example.invalid/x",
                text="会上决定先打穿筛选，必须拒绝清单体。",
            )
        )
        raise AssertionError("after_meeting must not ingest urls")
    except ValueError:
        pass


def test_read_article_boosts_concept_and_opposition() -> None:
    workspace = _workspace()
    query = "筛选的图谱会不会变成垃圾场"
    before = dict(workspace.retrieve._rank_claims(query, workspace.graph, None))
    workspace.run_play(
        RunPlayRequest(
            play_id="read_article",
            kind="markdown",
            title="无筛选会腐烂",
            text="知识图谱质量由拒绝率决定。主张必须挂证据才能进入已确认层。互相打架的结论不要偷偷合并。",
        )
    )
    assert workspace.workbench().play_context is not None
    assert workspace.workbench().play_context.play_id == "read_article"
    assert play_boost(workspace.graph, "claim_rot", "read_article") == 0.18
    assert play_boost(workspace.graph, "claim_evidence", "read_article") == 0.0
    after = dict(
        workspace.retrieve._rank_claims(
            query,
            workspace.graph,
            None,
            play_id=workspace._active_play_id(),
        )
    )
    assert after["claim_rot"] > before["claim_rot"]
    assert after["claim_rot"] - before["claim_rot"] > after.get("claim_evidence", 0) - before.get(
        "claim_evidence", 0
    )
    search = workspace.search_knowledge(query)
    rot = next(item for item in search.claims if item.id == "claim_rot")
    evidence = next((item for item in search.claims if item.id == "claim_evidence"), None)
    if evidence is not None:
        assert rot.score >= evidence.score


def test_after_meeting_boosts_working_notes_then_open_decisions() -> None:
    workspace = _workspace()
    query = "笔记变成可召回"
    before = dict(workspace.retrieve._rank_claims(query, workspace.graph, None))
    workspace.run_play(
        RunPlayRequest(
            play_id="after_meeting",
            text="会上决定先打穿筛选，必须拒绝清单体，不要全量入库。",
        )
    )
    assert play_boost(workspace.graph, "claim_recall", "after_meeting") == 0.08
    assert play_boost(workspace.graph, "claim_evidence", "after_meeting") == 0.0
    assert workspace._active_play_id() == "after_meeting"
    after = dict(
        workspace.retrieve._rank_claims(
            query,
            workspace.graph,
            None,
            play_id="after_meeting",
        )
    )
    assert after["claim_recall"] > before["claim_recall"]

    brief = workspace.workbench().brief
    assert brief is not None
    option = next(item for item in brief.options if "claim_rot" in item.supporting_claim_ids)
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=option.id, rationale="要对上出处，不能全收进库。"),
    )
    assert play_boost(workspace.graph, "claim_rot", "after_meeting") == 0.12
    recall_boost = play_boost(workspace.graph, "claim_recall", "after_meeting")
    assert recall_boost in {0.08, 0.18}


def test_play_context_expires_and_does_not_pad_unknown() -> None:
    workspace = _workspace()
    workspace.run_play(
        RunPlayRequest(
            play_id="read_article",
            kind="markdown",
            title="无筛选会腐烂",
            text="知识图谱质量由拒绝率决定。主张必须挂证据才能进入已确认层。互相打架的结论不要偷偷合并。",
        )
    )
    subgraph = workspace.retrieve.retrieve(
        "今晚月球菜单有什么汤",
        workspace.graph,
        play_id=workspace._active_play_id(),
    )
    assert subgraph.nodes == []
    workspace.play_context_at = datetime.now(timezone.utc) - timedelta(days=1)
    assert workspace._active_play_id() is None
    assert workspace.workbench().play_context is None
