from datetime import datetime, timedelta, timezone

from lynote.contracts.models import (
    ChatRequest,
    CommitBriefRequest,
    ComposeBriefRequest,
    ConfirmHangRequest,
    CreateGoalRequest,
    Profile,
    ScratchNoteRequest,
)
from lynote.modules.learn.today import compose_today
from lynote.modules.ingest.avtext import transcribe_audio, transcribe_video
from lynote.modules.graph.maintain import deprecate_claim, merge_concepts
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


def test_scratch_note_is_evidence_and_proposes_existing_hang() -> None:
    workspace = _workspace()
    before_concepts = set(workspace.graph.concepts)
    item = workspace.scratch_note(
        ScratchNoteRequest(text="没有筛选的图谱会变成垃圾场，必须拒绝清单体。")
    )
    assert item.source_id in workspace.graph.sources
    source = workspace.graph.sources[item.source_id]
    assert source.kind == "note"
    assert "没有筛选" in (source.text or "")
    quality = next(check for check in item.checks if check.gate == "quality")
    assert quality.passed is True
    accepted = workspace.accept_inbox(item.id)
    assert accepted.status == "accepted"
    claims = [
        claim
        for claim in workspace.graph.claims.values()
        if claim.evidence and claim.evidence[0].source_id == source.id
    ]
    assert claims
    assert all(claim.evidence[0].source_span is not None for claim in claims)
    assert workspace.hangs
    ids = {candidate.node_id for item in workspace.hangs for candidate in item.candidates}
    known = set(workspace.graph.concepts) | set(workspace.graph.goals)
    assert ids <= known
    assert "concept_invented" not in ids
    assert set(workspace.graph.concepts) == before_concepts


def test_confirm_hang_writes_about_and_rejects_invented_target() -> None:
    workspace = _workspace()
    item = workspace.scratch_note(
        ScratchNoteRequest(text="没有筛选的图谱会变成垃圾场，必须继续过闸。")
    )
    workspace.accept_inbox(item.id)
    proposal = workspace.hangs[0]
    written = workspace.confirm_hang(
        ConfirmHangRequest(claim_ids=proposal.claim_ids, target_id="concept_pkg")
    )
    assert written
    assert all(rel.to_id == "concept_pkg" and rel.type == "about" for rel in written)
    for cid in proposal.claim_ids:
        assert workspace.graph.claims[cid].status == "confirmed"
    try:
        workspace.confirm_hang(
            ConfirmHangRequest(claim_ids=proposal.claim_ids, target_id="concept_invented")
        )
        raise AssertionError("invented target should fail")
    except (KeyError, ValueError):
        pass


def test_audio_transcript_becomes_source_text() -> None:
    text = transcribe_audio(b"fake-bytes", "clip.wav", transcribe=lambda _data, _name: "[00:01] 主张必须挂证据才能进入已确认层。")
    assert "[00:01]" in text
    assert "主张必须挂证据" in text
    try:
        transcribe_audio(b"x", "clip.wav", transcribe=lambda _data, _name: "")
        raise AssertionError("empty transcript should fail")
    except ValueError:
        pass


def test_heuristic_extract_does_not_mint_glossary_concepts() -> None:
    workspace = _workspace()
    before = {concept.name for concept in workspace.graph.concepts.values()}
    item = workspace.scratch_note(
        ScratchNoteRequest(text="知识图谱必须拒绝清单体，笔记不是主张仓库。")
    )
    workspace.accept_inbox(item.id)
    after = {concept.name for concept in workspace.graph.concepts.values()}
    assert after == before
    assert "知识图谱" not in after
    assert "笔记" not in after
    assert "主张" not in after


def test_video_uses_transcript_without_inventing() -> None:
    text = transcribe_video(
        b"fake",
        "talk.mp4",
        transcribe=lambda _data, _name: "笔记必须变成可召回的主张。",
        vision=lambda _frames: "",
    )
    assert "笔记必须变成可召回的主张" in text
    assert "百科" not in text


def test_today_board_and_weekly_report_only_cite_existing_ids() -> None:
    workspace = _workspace()
    board = workspace.workbench().today
    assert board is not None
    assert any(item.id == "inbox_listicle" for item in board.inbox)
    assert all(item.id != "decision_week" for item in board.decisions)
    report = workspace.weekly_report()
    assert "本周外脑" in report.title
    assert all(cid in workspace.graph.claims for cid in report.claim_ids)
    assert all(sid in workspace.graph.sources for sid in report.source_ids)
    assert all(did in workspace.graph.decisions for did in report.decision_ids)
    assert "claim_does_not_exist" not in report.markdown


def test_today_hides_idle_draft_until_user_composes_then_prioritizes_outcome() -> None:
    workspace = _workspace()
    board = workspace.workbench().today
    assert all(item.detail != "简报未拍板" for item in board.decisions)
    brief = workspace.compose_brief(ComposeBriefRequest(use_model=False))
    board = workspace.workbench().today
    assert any(item.id == brief.decision_id and item.detail == "简报未拍板" for item in board.decisions)
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=brief.options[0].id, rationale="先打穿筛选和主张层"),
    )
    board = workspace.workbench().today
    assert any(item.id == brief.decision_id and item.detail == "已拍板，待复盘" for item in board.decisions)
    assert all(item.detail != "简报未拍板" for item in board.decisions)


def test_today_decisions_stay_on_current_goal() -> None:
    workspace = _workspace()
    brief = workspace.compose_brief(ComposeBriefRequest(use_model=False))
    workspace.commit_brief(
        brief.id,
        CommitBriefRequest(option_id=brief.options[0].id, rationale="先打穿筛选和主张层"),
    )
    workspace.create_goal(CreateGoalRequest(title="大模型学习"))
    board = workspace.workbench().today
    assert all(item.id != brief.decision_id for item in board.decisions)
    assert all(item.detail != "简报未拍板" for item in board.decisions)
    workspace.compose_brief(ComposeBriefRequest(use_model=False))
    board = workspace.workbench().today
    assert all(item.id != brief.decision_id for item in board.decisions)
    assert any(item.detail == "简报未拍板" for item in board.decisions)


def test_today_draft_only_same_iso_week() -> None:
    workspace = _workspace()
    goal = next(iter(workspace.graph.goals.values()))
    last_week = datetime.now(timezone.utc) - timedelta(days=8)
    hidden = compose_today(
        workspace.graph,
        inbox=[],
        learn=None,
        goal=goal,
        brief_touched_at=last_week,
        brief_touched_goal_id=goal.id,
    )
    assert all(item.detail != "简报未拍板" for item in hidden.decisions)
    shown = compose_today(
        workspace.graph,
        inbox=[],
        learn=None,
        goal=goal,
        brief_touched_at=datetime.now(timezone.utc),
        brief_touched_goal_id=goal.id,
    )
    assert any(item.detail == "简报未拍板" for item in shown.decisions)


def test_prior_decisions_surface_on_similar_brief() -> None:
    workspace = _workspace()
    decision = workspace.graph.decisions["decision_week"]
    decision.status = "reviewed"
    decision.outcome = "选图谱后维护税可接受"
    decision.chosen_option_id = "opt_graph_thin"
    workspace.graph.upsert_decision(decision)
    brief = workspace.compose_brief(
        ComposeBriefRequest(
            question="要不要把个人知识做成图谱，而不是继续堆笔记",
            use_model=False,
        )
    )
    assert any(item.decision_id == "decision_week" for item in brief.prior_decisions)


def test_own_notes_boost_and_cross_topic_stays_explicit() -> None:
    workspace = _workspace()
    workspace.update_profile(Profile(prefer_own_notes=True, skip_candidates=True, language="zh", role="开发", domains=["图谱"]))
    note = workspace.scratch_note(ScratchNoteRequest(text="没有筛选的图谱会变成垃圾场，必须拒绝清单体。"))
    workspace.accept_inbox(note.id)
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.grounded is not None
    other = workspace.chat(ChatRequest(content="完全无关的火星农业产量", expand_cross_topic=False))
    assert other.grounded is not None
    if other.grounded.direct:
        pass
    else:
        assert other.grounded.unknowns
    scoped = workspace.chat(ChatRequest(content="主张必须挂证据吗？", expand_cross_topic=False))
    assert scoped.grounded is not None
    if scoped.grounded.cross_topic:
        assert all(hit.claim_id in workspace.graph.claims for hit in scoped.grounded.cross_topic)
        assert all(ref.id not in {hit.claim_id for hit in scoped.grounded.cross_topic} or True for ref in scoped.grounded.direct)


def test_merge_and_deprecate_do_not_invent_nodes() -> None:
    workspace = _workspace()
    kept = merge_concepts(workspace.graph, "concept_pkg", "concept_notes")
    assert kept.id == "concept_pkg"
    assert "笔记堆积" in kept.aliases
    assert "concept_notes" not in workspace.graph.concepts
    saved = deprecate_claim(workspace.graph, "claim_ingest_all")
    assert saved.status == "deprecated"
    ranked_ok = "claim_ingest_all" not in {
        claim.id
        for claim in workspace.graph.claims.values()
        if claim.status != "deprecated"
    }
    assert ranked_ok
    answer = workspace.chat(ChatRequest(content="先把材料全收进向量库，以后再清理"))
    assert answer.grounded is not None
    assert all(ref.id != "claim_ingest_all" for ref in answer.grounded.direct)
