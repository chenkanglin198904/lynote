from lynote.contracts.models import Evidence, SourceSpan
from lynote.modules.graph.inspect import excerpt_from_evidence, inspect_node
from lynote.workspace import Workspace


def test_claim_excerpt_aligns_to_source() -> None:
    workspace = Workspace()
    detail = workspace.node_detail("claim_rot")
    assert detail.kind == "claim"
    assert detail.excerpts
    excerpt = detail.excerpts[0]
    assert excerpt.aligned
    assert excerpt.hit == "知识图谱质量由拒绝率决定。"
    source = workspace.graph.sources[excerpt.source_id]
    assert source.text == excerpt.before + excerpt.hit + excerpt.after
    assert excerpt.source_span is not None
    assert source.text[excerpt.source_span.start : excerpt.source_span.end] == excerpt.hit


def test_source_lists_citing_claims() -> None:
    workspace = Workspace()
    detail = workspace.node_detail("src_filter_essay")
    assert detail.kind == "source"
    claim_ids = {item.claim_id for item in detail.excerpts}
    assert "claim_rot" in claim_ids
    assert "claim_evidence" in claim_ids
    assert all(item.aligned for item in detail.excerpts)


def test_unknown_node_raises() -> None:
    workspace = Workspace()
    try:
        workspace.node_detail("node_missing")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_mismatched_quote_does_not_relocate() -> None:
    workspace = Workspace()
    source = workspace.graph.sources["src_filter_essay"]
    evidence = Evidence(
        source_id="src_filter_essay",
        quote="这段话不在原文里",
        source_span=SourceSpan(start=0, end=16),
    )
    excerpt = excerpt_from_evidence(workspace.graph, evidence, claim_id="claim_x")
    assert excerpt.aligned is False
    assert excerpt.source_span is not None
    assert excerpt.source_span.start == 0
    assert excerpt.source_span.end == 16
    assert excerpt.hit == (source.text or "")[0:16]
    assert excerpt.hit != evidence.quote


def test_missing_span_is_not_guessed() -> None:
    workspace = Workspace()
    excerpt = excerpt_from_evidence(
        workspace.graph,
        Evidence(source_id="src_filter_essay", quote="知识图谱质量由拒绝率决定。"),
    )
    assert excerpt.aligned is False
    assert excerpt.hit == ""
    assert excerpt.source_span is None
    inspect_node(workspace.graph, "claim_no_swarm")
    opposed = workspace.node_detail("claim_rot").opposed_claim_ids
    assert "claim_ingest_all" in opposed
