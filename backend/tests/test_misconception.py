from lynote.contracts.models import ChatRequest, GradeProbeRequest, Misconception
from lynote.modules.graph.store import InMemoryGraphStore
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


def _wrong(workspace: Workspace) -> str:
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    wrong = next(option for option in answer.probe.options if option.claim_id == "claim_ingest_all")
    graded = workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=wrong.id))
    assert graded.grade is not None
    assert graded.grade.verdict == "contrary"
    assert graded.grade.misconception_id
    return graded.grade.misconception_id


def test_wrong_answer_writes_misconception_on_correct_claim() -> None:
    workspace = _workspace()
    item_id = _wrong(workspace)
    item = workspace.graph.misconceptions[item_id]
    assert item.claim_id == "claim_rot"
    assert item.goal_id == "goal_graph_vs_notes"
    assert item.status == "active"
    assert item.count == 1
    assert item.verdict == "contrary"
    node = next(node for node in workspace.graph.snapshot().nodes if node.id == item_id)
    assert node.kind == "misconception"
    detail = workspace.node_detail(item_id)
    assert detail.claim_id == "claim_rot"
    assert "claim_does_not_exist" not in {node.id for node in detail.neighbors}


def test_same_claim_dedupes_and_increments() -> None:
    workspace = _workspace()
    first = _wrong(workspace)
    second = _wrong(workspace)
    assert first == second
    assert len(workspace.graph.misconceptions) == 1
    assert workspace.graph.misconceptions[first].count == 2


def test_related_question_recalls_misconception_unrelated_does_not() -> None:
    workspace = _workspace()
    item_id = _wrong(workspace)
    related = workspace.chat(ChatRequest(content="主张必须挂证据才能进入已确认层"))
    ids = {item.id for item in related.misconceptions}
    assert item_id in ids
    assert "你上次把" in related.content
    assert related.probe is not None
    assert "误区" in related.probe.prompt
    unrelated = workspace.chat(ChatRequest(content="今晚月球菜单有什么汤"))
    assert unrelated.misconceptions == []
    assert "你上次把" not in unrelated.content


def test_two_corrects_resolve_misconception() -> None:
    workspace = _workspace()
    item_id = _wrong(workspace)

    def _correct() -> None:
        answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
        assert answer.probe is not None
        option = next(item for item in answer.probe.options if item.claim_id == "claim_rot")
        graded = workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=option.id))
        assert graded.grade is not None
        assert graded.grade.verdict == "correct"

    _correct()
    assert workspace.graph.misconceptions[item_id].status == "active"
    assert workspace.graph.misconceptions[item_id].correct_streak == 1
    _correct()
    assert workspace.graph.misconceptions[item_id].status == "resolved"
    assert workspace.graph.misconceptions[item_id].correct_streak == 2


def test_manual_resolve_and_reject_invented_claim() -> None:
    workspace = _workspace()
    item_id = _wrong(workspace)
    saved = workspace.resolve_misconception(item_id)
    assert saved.status == "resolved"
    try:
        workspace.resolve_misconception("misc_missing")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
    try:
        workspace.graph.upsert_misconception(
            Misconception(
                id="misc_fake",
                text="编造的错法",
                claim_id="claim_does_not_exist",
                goal_id="goal_graph_vs_notes",
                last_seen_at="2026-09-17T00:00:00+00:00",
                verdict="gap",
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "existing claim" in str(exc)


def test_correct_first_time_does_not_create_misconception() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    option = next(item for item in answer.probe.options if item.claim_id == "claim_rot")
    workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=option.id))
    assert workspace.graph.misconceptions == {}


def test_empty_store_cannot_hang_misconception() -> None:
    store = InMemoryGraphStore()
    try:
        store.upsert_misconception(
            Misconception(
                id="misc_x",
                text="无主张",
                claim_id="claim_rot",
                goal_id="goal_x",
                last_seen_at="2026-09-17T00:00:00+00:00",
                verdict="gap",
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
