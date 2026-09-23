import pytest

from lynote.contracts.models import ChatRequest
from lynote.modules.learn.pack import pack_claims
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


def test_chapter_pack_keeps_opposition() -> None:
    workspace = _workspace()
    outline = workspace.workbench().outline
    assert outline is not None
    pkg = next(item for item in outline.chapters if item.id == "concept_pkg")
    assert any(item.id == "claim_rot" for item in pkg.pack_keep)
    rot = next(item for item in pkg.pack_keep if item.id == "claim_rot")
    assert "对立" in rot.reason
    assert rot.overridden is False


def test_loose_evidence_is_lookup_until_overridden() -> None:
    workspace = _workspace()
    outline = workspace.workbench().outline
    assert outline is not None
    evidence = next(item for item in outline.loose_claims if item.id == "claim_evidence")
    assert any(item.id == "claim_evidence" for item in evidence.pack_lookup)
    assert all(item.id != "claim_evidence" for item in evidence.pack_keep)
    workspace.set_claim_layer("claim_evidence", "keep")
    updated = workspace.workbench().outline
    assert updated is not None
    moved = next(item for item in updated.loose_claims if item.id == "claim_evidence")
    keep = next(item for item in moved.pack_keep if item.id == "claim_evidence")
    assert keep.overridden is True
    assert "你标成该内化" in keep.reason
    answer = workspace.chat(ChatRequest(content="主张必须挂证据才能进入已确认层"))
    assert answer.grounded is not None
    assert any(ref.id == "claim_evidence" for ref in answer.grounded.direct)


def test_override_lookup_demotes_keep() -> None:
    workspace = _workspace()
    workspace.set_claim_layer("claim_rot", "lookup")
    keep, lookup = pack_claims(
        workspace.graph,
        ["claim_rot"],
        workspace.practice,
        workspace.layer_overrides,
    )
    assert keep == []
    assert lookup[0].id == "claim_rot"
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.grounded is not None
    assert all(ref.id != "claim_rot" for ref in answer.grounded.direct)
    assert any(ref.id == "claim_rot" for ref in answer.grounded.lookup)


def test_clear_override_restores_auto() -> None:
    workspace = _workspace()
    workspace.set_claim_layer("claim_evidence", "keep")
    workspace.set_claim_layer("claim_evidence", None)
    assert "claim_evidence" not in workspace.layer_overrides
    keep, lookup = pack_claims(workspace.graph, ["claim_evidence"])
    assert keep == []
    assert lookup[0].id == "claim_evidence"


def test_cannot_keep_candidate() -> None:
    from lynote.contracts.models import Claim, Evidence, SourceSpan

    workspace = _workspace()
    workspace.graph.upsert_claim(
        Claim(
            id="claim_tmp_candidate",
            text="临时候选",
            polarity="asserts",
            confidence=0.4,
            status="candidate",
            evidence=[
                Evidence(
                    source_id="src_filter_essay",
                    quote="知识图谱质量由拒绝率决定。",
                    source_span=SourceSpan(start=0, end=13),
                )
            ],
        )
    )
    with pytest.raises(ValueError, match="未确认"):
        workspace.set_claim_layer("claim_tmp_candidate", "keep")
    with pytest.raises(KeyError):
        workspace.set_claim_layer("claim_does_not_exist", "keep")
