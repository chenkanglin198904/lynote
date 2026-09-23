from pathlib import Path

import pytest

from lynote.contracts.models import Claim, Decision, DecisionOption, Evidence, Source, SourceSpan
from lynote.modules.graph.persist import load_workspace_state, save_workspace_state
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.workspace import Workspace

kuzu = pytest.importorskip("kuzu")


def test_kuzu_roundtrip_claim(tmp_path: Path) -> None:
    from lynote.modules.graph.kuzu_store import KuzuGraphStore

    path = tmp_path / "graph.kuzu"
    store = KuzuGraphStore(path)
    try:
        source = Source(
            id="src_persist",
            kind="note",
            title="持久化",
            text="主张必须挂证据才能进入已确认层。",
            created_at="2026-09-16T00:00:00+00:00",
        )
        store.upsert_source(source)
        store.upsert_claim(
            Claim(
                id="claim_persist",
                text="主张必须挂证据才能进入已确认层",
                polarity="asserts",
                confidence=0.8,
                status="confirmed",
                evidence=[
                    Evidence(
                        source_id="src_persist",
                        quote="主张必须挂证据才能进入已确认层。",
                        source_span=SourceSpan(start=0, end=16),
                    )
                ],
            )
        )
    finally:
        store.close()

    restored = KuzuGraphStore(path)
    try:
        assert "src_persist" in restored.sources
        claim = restored.claims["claim_persist"]
        assert claim.evidence[0].source_span is not None
        assert claim.evidence[0].source_span.start == 0
        assert claim.text == "主张必须挂证据才能进入已确认层"
    finally:
        restored.close()


def test_workspace_restores_without_reseeding(tmp_path: Path) -> None:
    from lynote.modules.graph.kuzu_store import KuzuGraphStore

    graph_path = tmp_path / "ws.kuzu"
    state_path = tmp_path / "workspace.json"
    first = Workspace(graph=KuzuGraphStore(graph_path), persist=True, state_path=state_path)
    item_id = next(iter(first.inbox))
    first.reject_inbox(item_id)
    claim_ids = set(first.graph.claims)
    inbox_count = len(first.inbox)
    first.graph.close()

    second = Workspace(graph=KuzuGraphStore(graph_path), persist=True, state_path=state_path)
    try:
        assert second.inbox[item_id].status == "rejected"
        assert set(second.graph.claims) == claim_ids
        assert len(second.inbox) == inbox_count
        assert second.brief is not None
    finally:
        second.graph.close()


def test_workspace_json_roundtrip(tmp_path: Path) -> None:
    workspace = Workspace(graph=InMemoryGraphStore(), persist=False)
    path = tmp_path / "workspace.json"
    save_workspace_state(
        path,
        workspace.inbox,
        workspace.messages,
        workspace.brief,
        workspace.practice,
        brief_touched_at="2026-09-22T08:00:00+00:00",
        brief_touched_goal_id="goal_graph_vs_notes",
    )
    inbox, messages, brief, practice, profile, hangs, touched, touched_goal, overrides, play_context = (
        load_workspace_state(path)
    )
    assert set(inbox) == set(workspace.inbox)
    assert messages
    assert brief is not None
    assert workspace.brief is not None
    assert brief.id == workspace.brief.id
    assert brief.question == workspace.brief.question
    assert practice == {}
    assert profile.prefer_own_notes is True
    assert hangs == []
    assert touched == "2026-09-22T08:00:00+00:00"
    assert touched_goal == "goal_graph_vs_notes"
    assert overrides == {}
    assert play_context is None


def test_kuzu_roundtrip_decision_outcome(tmp_path: Path) -> None:
    from lynote.modules.graph.kuzu_store import KuzuGraphStore

    path = tmp_path / "decision.kuzu"
    store = KuzuGraphStore(path)
    try:
        store.upsert_decision(
            Decision(
                id="decision_persist",
                goal_id="goal_x",
                question="要不要？",
                options=[
                    DecisionOption(
                        id="opt_a",
                        label="做",
                        summary="做",
                        supporting_claim_ids=[],
                    )
                ],
                chosen_option_id="opt_a",
                outcome="做了，有效。",
                status="reviewed",
            )
        )
    finally:
        store.close()

    restored = KuzuGraphStore(path)
    try:
        decision = restored.decisions["decision_persist"]
        assert decision.status == "reviewed"
        assert decision.outcome == "做了，有效。"
        assert decision.chosen_option_id == "opt_a"
    finally:
        restored.close()
