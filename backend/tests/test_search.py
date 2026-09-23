from lynote.contracts.models import ChatRequest, CreateGoalRequest
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


def test_search_hits_concept_and_claim() -> None:
    workspace = _workspace()
    result = workspace.search_knowledge("个人知识图谱")
    assert result.unknown is False
    assert any(hit.id == "concept_pkg" for hit in result.concepts)
    rot = workspace.search_knowledge("没有筛选的图谱")
    assert any(hit.id == "claim_rot" for hit in rot.claims)
    assert any(hit.id == "src_filter_essay" for hit in rot.sources)
    assert rot.claims[0].path_ids[0] == "goal_graph_vs_notes"


def test_search_unknown_does_not_invent() -> None:
    result = _workspace().search_knowledge("今晚月球菜单有什么汤")
    assert result.unknown is True
    assert result.concepts == []
    assert result.claims == []
    assert result.sources == []


def test_search_stays_in_active_topic() -> None:
    workspace = _workspace()
    workspace.create_goal(CreateGoalRequest(title="大模型学习"))
    result = workspace.search_knowledge("没有筛选的图谱")
    assert result.unknown is True
    assert result.claims == []
    assert result.concepts == []


def test_chat_grounded_four_sections() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.grounded is not None
    assert answer.grounded.direct
    allowed = set(workspace.graph.claims) | set(workspace.graph.concepts) | set(workspace.graph.sources)
    for ref in answer.grounded.direct + answer.grounded.lookup + answer.grounded.evidence + answer.grounded.related:
        assert ref.id in allowed
    assert "claim_does_not_exist" not in answer.claim_ids
    assert "【直答】" in answer.content
    assert "【需要时再查】" in answer.content
    assert "【依据】" in answer.content
    assert "【联想】" in answer.content
    assert "【边界】" in answer.content
    cited = {ref.id for ref in answer.grounded.direct + answer.grounded.related}
    assert "claim_rot" in cited
    assert "claim_ingest_all" in cited
    rot = next(ref for ref in answer.grounded.direct if ref.id == "claim_rot")
    assert rot.layer == "keep"


def test_search_layers_keep_before_lookup() -> None:
    workspace = _workspace()
    result = workspace.search_knowledge("没有筛选的图谱")
    rot = next(hit for hit in result.claims if hit.id == "claim_rot")
    assert rot.layer == "keep"
    evidence = workspace.search_knowledge("主张必须挂证据")
    hit = next(item for item in evidence.claims if item.id == "claim_evidence")
    assert hit.layer == "lookup"
    keep_ids = [item.id for item in evidence.claims if item.layer == "keep"]
    lookup_ids = [item.id for item in evidence.claims if item.layer == "lookup"]
    if keep_ids and lookup_ids:
        first_lookup = min(i for i, item in enumerate(evidence.claims) if item.layer == "lookup")
        last_keep = max(i for i, item in enumerate(evidence.claims) if item.layer == "keep")
        assert last_keep < first_lookup


def test_chat_lookup_does_not_invent_principle() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="主张必须挂证据才能进入已确认层"))
    assert answer.grounded is not None
    assert all(ref.id != "claim_evidence" for ref in answer.grounded.direct)
    assert any(ref.id == "claim_evidence" for ref in answer.grounded.lookup)
    evidence = next(ref for ref in answer.grounded.lookup if ref.id == "claim_evidence")
    assert evidence.layer == "lookup"
    assert any("不能编一条原理" in item for item in answer.grounded.unknowns)


def test_chat_practiced_claim_promotes_to_keep() -> None:
    from lynote.contracts.models import PracticeStat

    workspace = _workspace()
    workspace.practice["goal_graph_vs_notes:claim_evidence"] = PracticeStat(
        goal_id="goal_graph_vs_notes",
        claim_id="claim_evidence",
        correct_count=2,
    )
    answer = workspace.chat(ChatRequest(content="主张必须挂证据才能进入已确认层"))
    assert answer.grounded is not None
    assert any(ref.id == "claim_evidence" for ref in answer.grounded.direct)
    promoted = next(ref for ref in answer.grounded.direct if ref.id == "claim_evidence")
    assert promoted.layer == "keep"


def test_chat_pinned_lookup_still_in_direct() -> None:
    workspace = _workspace()
    answer = workspace.chat(
        ChatRequest(
            content="主张必须挂证据才能进入已确认层",
            pinned_node_ids=["claim_evidence"],
        )
    )
    assert answer.grounded is not None
    cited = [ref.id for ref in answer.grounded.direct if ref.kind == "claim"]
    assert "claim_evidence" in cited
    pinned = next(ref for ref in answer.grounded.direct if ref.id == "claim_evidence")
    assert pinned.layer == "lookup"


def test_chat_unknown_empty_claims() -> None:
    workspace = _workspace()
    answer = workspace.chat(ChatRequest(content="今晚月球菜单有什么汤"))
    assert answer.unknowns
    assert answer.claim_ids == []
    assert answer.grounded is not None
    assert answer.grounded.direct == []
    assert answer.grounded.lookup == []
    assert answer.grounded.evidence == []


def test_chat_on_empty_topic_is_unknown() -> None:
    workspace = _workspace()
    workspace.create_goal(CreateGoalRequest(title="大模型学习"))
    answer = workspace.chat(ChatRequest(content="没有筛选的图谱会怎样？"))
    assert answer.claim_ids == []
    assert answer.unknowns
