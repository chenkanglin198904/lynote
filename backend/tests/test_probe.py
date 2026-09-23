from lynote.contracts.models import ChatRequest, GradeProbeRequest, ChatMessage, GroundedAnswer, GroundedRef
from lynote.modules.tutor.probe import attach_probe
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


def test_explanation_asks_one_choice_probe() -> None:
    answer = _workspace().chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    assert answer.probe.status == "open"
    assert answer.probe.kind == "choice"
    assert answer.probe.target_claim_id == "claim_rot"
    claim_ids = {option.claim_id for option in answer.probe.options if option.claim_id}
    assert claim_ids == {"claim_rot", "claim_ingest_all"}
    assert answer.grade is None


def test_unknown_chat_has_no_probe() -> None:
    answer = _workspace().chat(ChatRequest(content="今晚月球菜单有什么汤"))
    assert answer.probe is None
    assert answer.grade is None


def test_grade_correct_choice() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    correct = next(option for option in answer.probe.options if option.claim_id == "claim_rot")
    graded = workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=correct.id))
    assert graded.grade is not None
    assert graded.grade.verdict == "correct"
    assert graded.probe is not None and graded.probe.status == "graded"
    assert graded.grade.cited_claim_ids == ["claim_rot"]
    assert "claim_does_not_exist" not in graded.grade.cited_claim_ids
    assert "没有筛选的图谱会变成垃圾场" in graded.grade.correction


def test_grade_contrary_choice() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    wrong = next(option for option in answer.probe.options if option.claim_id == "claim_ingest_all")
    graded = workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=wrong.id))
    assert graded.grade is not None
    assert graded.grade.verdict == "contrary"
    assert "claim_rot" in graded.grade.cited_claim_ids
    assert "claim_ingest_all" in graded.grade.cited_claim_ids
    assert "反了" in graded.grade.correction


def test_grade_unsure_is_gap() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    unsure = next(option for option in answer.probe.options if option.claim_id is None)
    graded = workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=unsure.id))
    assert graded.grade is not None
    assert graded.grade.verdict == "gap"
    assert graded.grade.cited_claim_ids == ["claim_rot"]


def test_short_probe_grades_paraphrase_and_miss() -> None:
    workspace = _workspace()
    seed = ChatMessage(
        id="msg_evidence",
        role="assistant",
        content="讲解",
        grounded=GroundedAnswer(
            direct=[
                GroundedRef(
                    id="claim_evidence",
                    kind="claim",
                    label="主张必须挂证据才能进入已确认层",
                    status="confirmed",
                )
            ],
            unknowns=[],
        ),
    )
    probed = attach_probe(seed, workspace.graph)
    assert probed.probe is not None
    assert probed.probe.kind == "short"
    workspace.messages.append(probed)
    hit = workspace.grade_probe(
        probed.probe.id,
        GradeProbeRequest(text="没有证据的主张不能进入已确认层"),
    )
    assert hit.grade is not None
    assert hit.grade.verdict == "correct"
    workspace2 = _workspace()
    probed2 = attach_probe(seed.model_copy(deep=True), workspace2.graph)
    assert probed2.probe is not None
    workspace2.messages.append(probed2)
    miss = workspace2.grade_probe(probed2.probe.id, GradeProbeRequest(text="今晚月亮很圆"))
    assert miss.grade is not None
    assert miss.grade.verdict == "gap"


def test_grade_rejects_second_attempt_and_invented_option() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    correct = next(option for option in answer.probe.options if option.claim_id == "claim_rot")
    workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=correct.id))
    try:
        workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=correct.id))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "已经批改" in str(exc)
    try:
        workspace.grade_probe("probe_missing", GradeProbeRequest(option_id=correct.id))
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
