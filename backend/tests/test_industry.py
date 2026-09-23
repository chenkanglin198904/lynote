from lynote.contracts.models import Profile, ScratchNoteRequest
from lynote.modules.learn.industry import apply_industry_hints
from lynote.providers.embeddings import HashingEmbedder
from lynote.providers.vectors import InMemoryVectorStore
from lynote.modules.retrieve.service import RetrieveService
from lynote.providers.websearch import SearchHit, search_web
from lynote.workspace import Workspace


def _workspace() -> Workspace:
    return Workspace(
        retrieve=RetrieveService(
            embedder=HashingEmbedder(dim=64),
            vectors=InMemoryVectorStore(),
            min_score=0.08,
        )
    )


def test_industry_search_ranks_existing_and_does_not_invent() -> None:
    workspace = _workspace()
    item = workspace.scratch_note(
        ScratchNoteRequest(text="没有筛选的图谱会变成垃圾场，必须继续过闸。")
    )
    workspace.accept_inbox(item.id)
    assert workspace.hangs
    before = set(workspace.graph.concepts)
    names_before = {concept.name for concept in workspace.graph.concepts.values()}
    enriched = apply_industry_hints(
        workspace.graph,
        workspace.hangs[0],
        goal=next(goal for goal in workspace.graph.goals.values() if goal.status == "active"),
        profile=Profile(domains=["个人知识"]),
        search=lambda _query, _limit: [
            SearchHit(
                "知识图谱拒绝率",
                "https://example.org/pkg",
                "个人知识图谱质量由拒绝率决定，主张必须挂证据",
            ),
            SearchHit(
                "行业本体手册",
                "https://example.org/ontology",
                "上层本体 OWL 与行业分类标准不能直接当个人目录",
            ),
            SearchHit("内网", "http://localhost/secret", "不该当作行业依据"),
        ],
    )
    assert set(workspace.graph.concepts) == before
    assert {concept.name for concept in workspace.graph.concepts.values()} == names_before
    assert "行业本体手册" not in names_before
    assert not any(concept.name == "行业本体手册" for concept in workspace.graph.concepts.values())
    ids = {candidate.node_id for candidate in enriched.candidates}
    assert ids <= set(workspace.graph.concepts) | set(workspace.graph.goals)
    assert "concept_pkg" in ids
    urls = {hint.url for hint in enriched.industry_hints}
    assert "https://example.org/pkg" in urls
    assert not any("localhost" in url for url in urls)
    matched = next(hint for hint in enriched.industry_hints if hint.url.endswith("/pkg"))
    assert matched.matched_node_id == "concept_pkg"
    ontology = next(hint for hint in enriched.industry_hints if hint.url.endswith("/ontology"))
    assert ontology.matched_node_id is None or ontology.matched_node_id in workspace.graph.concepts


def test_industry_search_failure_does_not_block_hang() -> None:
    workspace = _workspace()
    item = workspace.scratch_note(
        ScratchNoteRequest(text="没有筛选的图谱会变成垃圾场，必须拒绝清单体。")
    )
    workspace.accept_inbox(item.id)
    proposal = workspace.hangs[0]

    def boom(_query: str, _limit: int):
        raise OSError("search down")

    enriched = apply_industry_hints(workspace.graph, proposal, search=boom)
    assert enriched.claim_ids == proposal.claim_ids
    assert enriched.candidates
    assert enriched.industry_hints == []


def test_search_web_drops_non_http_and_loopback() -> None:
    hits = search_web(
        "个人知识图谱",
        5,
        search=lambda _q, _n: [
            SearchHit("ok", "https://example.org/a", "a"),
            SearchHit("file", "file:///tmp/x", "no"),
            SearchHit("loop", "http://127.0.0.1/x", "no"),
        ],
    )
    assert [hit.url for hit in hits] == ["https://example.org/a"]
