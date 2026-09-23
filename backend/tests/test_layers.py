from lynote.contracts.models import Claim, Evidence, PracticeStat, SourceSpan
from lynote.modules.retrieve.layers import claim_layer
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


def test_opposition_is_keep() -> None:
    workspace = _workspace()
    rot = workspace.graph.claims["claim_rot"]
    assert claim_layer(workspace.graph, rot) == "keep"


def test_confirmed_evidence_without_opposition_is_lookup() -> None:
    workspace = _workspace()
    evidence = workspace.graph.claims["claim_evidence"]
    assert claim_layer(workspace.graph, evidence) == "lookup"


def test_practiced_claim_is_keep() -> None:
    workspace = _workspace()
    evidence = workspace.graph.claims["claim_evidence"]
    practice = {
        "goal_graph_vs_notes:claim_evidence": PracticeStat(
            goal_id="goal_graph_vs_notes",
            claim_id="claim_evidence",
            correct_count=2,
        )
    }
    assert claim_layer(workspace.graph, evidence, practice) == "keep"


def test_override_forces_keep() -> None:
    workspace = _workspace()
    evidence = workspace.graph.claims["claim_evidence"]
    assert claim_layer(workspace.graph, evidence) == "lookup"
    assert claim_layer(workspace.graph, evidence, overrides={"claim_evidence": "keep"}) == "keep"
    rot = workspace.graph.claims["claim_rot"]
    assert claim_layer(workspace.graph, rot, overrides={"claim_rot": "lookup"}) == "lookup"


def test_candidate_and_spanless_are_lookup() -> None:
    workspace = _workspace()
    candidate = Claim(
        id="claim_tmp_candidate",
        text="临时候选",
        polarity="asserts",
        confidence=0.5,
        status="candidate",
        evidence=[
            Evidence(
                source_id="src_filter_essay",
                quote="知识图谱质量由拒绝率决定。",
                source_span=SourceSpan(start=0, end=13),
            )
        ],
    )
    spanless = Claim(
        id="claim_tmp_spanless",
        text="没有定位的确认主张",
        polarity="asserts",
        confidence=0.9,
        status="confirmed",
        evidence=[Evidence(source_id="src_filter_essay", quote="知识图谱质量由拒绝率决定。")],
    )
    assert claim_layer(workspace.graph, candidate) == "lookup"
    assert claim_layer(workspace.graph, spanless) == "lookup"
