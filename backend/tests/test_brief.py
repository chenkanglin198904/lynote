from lynote.contracts.models import ComposeBriefRequest
from lynote.modules.brief.service import BriefService
from lynote.workspace import Workspace


def test_compose_brief_only_cites_subgraph_claims() -> None:
    workspace = Workspace()
    brief = workspace.workbench().brief
    assert brief is not None
    assert brief.options
    assert brief.skeptic
    allowed = set(workspace.graph.claims)
    for option in brief.options:
        assert option.supporting_claim_ids
        assert set(option.supporting_claim_ids) <= allowed
    assert set(brief.evidence_claim_ids) <= allowed


def test_compose_drops_invented_claim_ids() -> None:
    def fake(_system: str, _user: str) -> dict:
        return {
            "options": [
                {
                    "label": "伪造证据的选项",
                    "summary": "引用了不存在的主张",
                    "supporting_claim_ids": ["claim_does_not_exist"],
                },
                {
                    "label": "用真主张",
                    "summary": "可以核对",
                    "supporting_claim_ids": ["claim_rot"],
                },
            ],
            "skeptic": "对立主张提醒筛选纪律。",
            "unknowns": ["执行成本未知"],
            "recommendation": "选真主张那条",
        }

    workspace = Workspace(briefing=BriefService(complete_json=fake))
    brief = workspace.compose_brief(ComposeBriefRequest())
    cited = {cid for option in brief.options for cid in option.supporting_claim_ids}
    assert "claim_does_not_exist" not in cited
    assert "claim_rot" in cited
    assert brief.skeptic.startswith("[模型]")


def test_empty_subgraph_does_not_invent_options() -> None:
    workspace = Workspace()
    brief = workspace.compose_brief(
        ComposeBriefRequest(question="今晚月球食堂供应什么汤")
    )
    invented = [
        option
        for option in brief.options
        if any(cid not in workspace.graph.claims for cid in option.supporting_claim_ids)
    ]
    assert invented == []
    if not brief.options:
        assert brief.unknowns
