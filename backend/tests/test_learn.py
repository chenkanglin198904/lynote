from lynote.contracts.models import (
    ChatRequest,
    Claim,
    Concept,
    Evidence,
    GradeProbeRequest,
    IngestSourceRequest,
    Relation,
    SourceSpan,
    StartReviewRequest,
)
from lynote.modules.graph.ids import new_id
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


def test_unopposed_concept_is_missing() -> None:
    workspace = _workspace()
    concept = Concept(id="concept_lonely", name="确认层", definition="只有一条主张")
    workspace.graph.upsert_concept(concept)
    claim = Claim(
        id="claim_lonely",
        text="确认层只需要感觉对就行",
        polarity="asserts",
        confidence=0.5,
        status="confirmed",
        evidence=[
            Evidence(
                source_id="src_filter_essay",
                quote="主张必须挂证据才能进入已确认层。",
                source_span=SourceSpan(start=45, end=61),
            )
        ],
    )
    workspace.graph.upsert_claim(claim)
    workspace.graph.upsert_relation(
        Relation(id=new_id("rel"), from_id=claim.id, to_id=concept.id, type="about")
    )
    workspace.graph.upsert_relation(
        Relation(id=new_id("rel"), from_id=claim.id, to_id="goal_graph_vs_notes", type="about")
    )
    learn = workspace.workbench().learn
    assert learn is not None
    lonely = next(item for item in learn.concepts if item.id == "concept_lonely")
    assert lonely.status == "missing"
    assert "对立" in lonely.reason
    assert any(gap.id == "concept_lonely" and gap.need == "opposition" for gap in learn.gaps)
    evidence = next(item for item in learn.claims if item.id == "claim_evidence")
    assert evidence.status == "missing"
    rot = next(item for item in learn.claims if item.id == "claim_rot")
    assert rot.status == "ready"
    notes = next(item for item in learn.concepts if item.id == "concept_notes")
    assert notes.status == "missing"
    assert learn.contrasts
    pair = learn.contrasts[0]
    assert {pair.left_id, pair.right_id} == {"claim_rot", "claim_ingest_all"}
    assert "claim_does_not_exist" not in {item.id for item in learn.claims}


def test_contrary_makes_weak_and_due_review() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.probe is not None
    wrong = next(option for option in answer.probe.options if option.claim_id == "claim_ingest_all")
    workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=wrong.id))
    learn = workspace.workbench().learn
    assert learn is not None
    rot = next(item for item in learn.claims if item.id == "claim_rot")
    assert rot.status == "weak"
    assert any(item.claim_id == "claim_rot" for item in learn.reviews)
    review = workspace.start_review(StartReviewRequest())
    assert review.probe is not None
    assert review.probe.target_claim_id == "claim_rot"
    assert review.grounded is not None
    assert all(ref.id in workspace.graph.claims for ref in review.grounded.direct)


def test_two_corrects_master_claim() -> None:
    workspace = _workspace()
    for _ in range(2):
        answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
        assert answer.probe is not None
        option = next(item for item in answer.probe.options if item.claim_id == "claim_rot")
        workspace.grade_probe(answer.probe.id, GradeProbeRequest(option_id=option.id))
    learn = workspace.workbench().learn
    assert learn is not None
    rot = next(item for item in learn.claims if item.id == "claim_rot")
    assert rot.status == "mastered"
    assert not any(item.claim_id == "claim_rot" for item in learn.reviews)


def test_gap_filling_source_ranks_above_listicle() -> None:
    workspace = _workspace()
    filler = workspace.ingest_source(
        IngestSourceRequest(
            kind="note",
            title="确认层需要对立主张",
            text=(
                "主张必须挂证据才能进入已确认层。有人反对说先凭感觉确认即可，"
                "两边互相冲突，应该把对立观点一起留下，而不是偷偷合并。"
            ),
        )
    )
    assert filler.gap_score > 0
    wb = workspace.workbench()
    pending = [item for item in wb.inbox if item.status == "pending"]
    assert pending[0].id == filler.id
    listicle = next(item for item in wb.inbox if item.id == "inbox_listicle")
    assert listicle.gap_score == 0
    assert filler.gap_score > listicle.gap_score


def test_review_without_due_is_rejected() -> None:
    workspace = _workspace()
    try:
        workspace.start_review(StartReviewRequest())
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "巩固" in str(exc)
