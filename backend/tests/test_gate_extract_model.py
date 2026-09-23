from lynote.contracts.models import Claim, Evidence, ConfirmHangRequest, IngestSourceRequest
from lynote.llm.parse import parse_json_object
from lynote.modules.extract.service import ExtractService
from lynote.modules.extract.spans import locate_span
from lynote.modules.gate.service import GateService
from lynote.modules.graph.store import InMemoryGraphStore
from lynote.workspace import Workspace


def test_parse_json_object_strips_fence() -> None:
    payload = parse_json_object("```json\n{\"ok\": true}\n```")
    assert payload == {"ok": True}


def test_locate_span_handles_whitespace() -> None:
    text = "主张必须挂证据\n才能进入已确认层。"
    span = locate_span(text, "主张必须挂证据 才能进入已确认层。")
    assert span is not None
    assert text[span.start : span.end].replace("\n", "") == "主张必须挂证据才能进入已确认层。"


def test_store_rejects_claim_without_span() -> None:
    store = InMemoryGraphStore()
    try:
        store.upsert_claim(
            Claim(
                id="claim_bad",
                text="无出处",
                polarity="asserts",
                confidence=0.5,
                status="candidate",
                evidence=[Evidence(source_id="src_x", quote="无出处")],
            )
        )
    except ValueError as exc:
        assert "source_span" in str(exc)
    else:
        raise AssertionError("expected source_span error")


def test_gate_model_notes_but_code_verdict() -> None:
    def fake(_system: str, _user: str) -> dict:
        return {
            "checks": [
                {"gate": "goal_alignment", "passed": True, "note": "对准当前的图谱问题"},
                {"gate": "quality", "passed": False, "note": "没有可核对的论证，只是口号"},
                {"gate": "novelty", "passed": True, "note": "模型以为是新的"},
                {"gate": "actionability", "passed": True, "note": "可能改变选项"},
                {"gate": "maintenance_cost", "passed": True, "note": "实体不多"},
            ]
        }

    workspace = Workspace(gate=GateService(complete_json=fake))
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="note",
            title="随便一篇",
            text="这是一段超过四十字的正文，用来触发模型闸门而不是过短拒绝规则，内容在谈知识图谱与主张。",
        )
    )
    assert item.verdict == "reject"
    quality = next(check for check in item.checks if check.gate == "quality")
    assert quality.passed is False
    assert "口号" in quality.note
    assert quality.note.startswith("[模型]")


def test_gate_duplicate_title_overrides_model() -> None:
    def fake(_system: str, _user: str) -> dict:
        return {
            "checks": [
                {"gate": "goal_alignment", "passed": True, "note": "相关"},
                {"gate": "quality", "passed": True, "note": "有论证"},
                {"gate": "novelty", "passed": True, "note": "模型误判为新"},
                {"gate": "actionability", "passed": True, "note": "可行动"},
                {"gate": "maintenance_cost", "passed": True, "note": "可维护"},
            ]
        }

    workspace = Workspace(gate=GateService(complete_json=fake))
    payload = IngestSourceRequest(
        kind="note",
        title="本周笔记：信息越存越找不到",
        text="笔记必须变成可召回的主张。没有证据的节点不要进入已确认层。个人知识图谱应该拒绝营销稿。",
    )
    item = workspace.ingest_source(payload)
    novelty = next(check for check in item.checks if check.gate == "novelty")
    assert item.verdict == "reject"
    assert novelty.passed is False
    assert "重复" in novelty.note


def test_extract_model_keeps_locatable_span() -> None:
    quote = "没有证据的节点不要进入已确认层。"

    def fake(_system: str, _user: str) -> dict:
        return {
            "concepts": [{"name": "主张", "definition": "可核验判断", "domain": "个人知识"}],
            "claims": [
                {
                    "text": "没有证据不能进入已确认层",
                    "polarity": "asserts",
                    "confidence": 0.8,
                    "quote": quote,
                    "about": ["主张", "过闸"],
                }
            ],
        }

    workspace = Workspace(extract=ExtractService(complete_json=fake))
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="note",
            title="主张层比文件夹更重要",
            text="笔记必须变成可召回的主张。没有证据的节点不要进入已确认层。",
        )
    )
    before = set(workspace.graph.claims)
    workspace.accept_inbox(item.id)
    new_claims = [workspace.graph.claims[cid] for cid in set(workspace.graph.claims) - before]
    assert len(new_claims) == 1
    evidence = new_claims[0].evidence[0]
    assert evidence.source_span is not None
    source = workspace.graph.sources[item.source_id]
    body = source.text or ""
    assert body[evidence.source_span.start : evidence.source_span.end] == quote
    assert not any(concept.name == "主张" for concept in workspace.graph.concepts.values())
    assert workspace.hangs
    assert "主张" in workspace.hangs[0].proposed_names
    assert "过闸" not in workspace.hangs[0].proposed_names
    written = workspace.confirm_hang(
        ConfirmHangRequest(claim_ids=workspace.hangs[0].claim_ids, new_name="主张")
    )
    assert written
    created = next(concept for concept in workspace.graph.concepts.values() if concept.name == "主张")
    assert all(rel.to_id == created.id and rel.type == "about" for rel in written)
    try:
        workspace.confirm_hang(
            ConfirmHangRequest(claim_ids=list(workspace.graph.claims), new_name="过闸")
        )
        raise AssertionError("unproposed name should fail")
    except ValueError:
        pass
    assert not any(concept.name == "过闸" for concept in workspace.graph.concepts.values())


def test_extract_model_drops_unlocatable_quote() -> None:
    def fake(_system: str, _user: str) -> dict:
        return {
            "concepts": [],
            "claims": [
                {
                    "text": "火星上已经有人定居",
                    "polarity": "asserts",
                    "confidence": 0.99,
                    "quote": "这段原文里根本没有的话",
                }
            ],
        }

    workspace = Workspace(extract=ExtractService(complete_json=fake))
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="note",
            title="主张层比文件夹更重要",
            text="笔记必须变成可召回的主张。没有证据的节点不要进入已确认层。",
        )
    )
    before = set(workspace.graph.claims)
    workspace.accept_inbox(item.id)
    assert set(workspace.graph.claims) == before
