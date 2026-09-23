from lynote.llm.client import apply_caller


def test_apply_caller_adds_field() -> None:
    body = apply_caller({"model": "gpt-5-mini"}, "lynote")
    assert body["caller"] == "lynote"


def test_apply_caller_skips_blank() -> None:
    body = apply_caller({"model": "gpt-5-mini"}, "  ")
    assert "caller" not in body
