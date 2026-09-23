from lynote.contracts.models import IngestSourceRequest
from lynote.modules.ingest.fetch import FetchedPage, assert_http_url
from lynote.modules.ingest.htmltext import html_to_text
from lynote.modules.ingest.service import IngestService
from lynote.workspace import Workspace


def test_html_to_text_strips_script_and_keeps_title() -> None:
    page = html_to_text(
        "<html><head><title>无筛选的图谱会腐烂</title><script>alert(1)</script></head>"
        "<body><p>知识图谱质量由拒绝率决定。</p></body></html>"
    )
    assert page.title == "无筛选的图谱会腐烂"
    assert "拒绝率" in page.text
    assert "alert" not in page.text


def test_url_ingest_uses_fetched_html() -> None:
    html = (
        "<html><head><title>无筛选的图谱会腐烂</title></head>"
        "<body><p>知识图谱质量由拒绝率决定。主张必须挂证据才能进入已确认层。</p></body></html>"
    )

    def fake(_uri: str) -> FetchedPage:
        return FetchedPage(
            url="https://example.com/filter",
            content_type="text/html",
            data=html.encode(),
            text=html,
        )

    workspace = Workspace(ingest=IngestService(fetch=fake))
    item = workspace.ingest_source(
        IngestSourceRequest(kind="url", uri="https://example.com/filter")
    )
    source = workspace.graph.sources[item.source_id]
    assert source.kind == "url"
    assert source.title == "无筛选的图谱会腐烂"
    assert "拒绝率" in (source.text or "")


def test_file_url_is_rejected() -> None:
    try:
        assert_http_url("file:///etc/passwd")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "http" in str(exc)


def test_markdown_ingest_keeps_body() -> None:
    workspace = Workspace()
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="markdown",
            title="主张层",
            text="# 主张\n\n笔记必须变成可召回的主张。没有证据的节点不要进入已确认层。",
        )
    )
    source = workspace.graph.sources[item.source_id]
    assert source.kind == "markdown"
    assert "可召回的主张" in (source.text or "")


def test_upload_markdown_file() -> None:
    workspace = Workspace()
    item = workspace.ingest_upload(
        "filter.md",
        "# 筛选\n\n知识图谱质量由拒绝率决定。".encode("utf-8"),
    )
    source = workspace.graph.sources[item.source_id]
    assert source.kind == "markdown"
    assert source.title == "filter"
    assert "拒绝率" in (source.text or "")


def test_upload_rejects_unknown_type() -> None:
    workspace = Workspace()
    try:
        workspace.ingest_upload("payload.exe", b"MZ")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "只接受" in str(exc)


def test_pdf_ingest_keeps_extracted_body() -> None:
    workspace = Workspace()
    item = workspace.ingest_source(
        IngestSourceRequest(
            kind="pdf",
            title="PDF 主张",
            text="主张必须挂证据才能进入已确认层。",
            uri="claims.pdf",
        )
    )
    source = workspace.graph.sources[item.source_id]
    assert source.kind == "pdf"
    assert "主张必须挂证据" in (source.text or "")


def test_corrupt_pdf_is_rejected() -> None:
    workspace = Workspace()
    try:
        workspace.ingest_upload("broken.pdf", b"%PDF-1.1 not a real file")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "PDF" in str(exc) or "无法" in str(exc)


def test_blank_pdf_is_rejected() -> None:
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = BytesIO()
    writer.write(buf)
    workspace = Workspace()
    try:
        workspace.ingest_upload("empty.pdf", buf.getvalue())
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "抽不出" in str(exc)


def test_scanned_pdf_uses_vision_transcript() -> None:
    from io import BytesIO

    from pypdf import PdfWriter

    from lynote.modules.ingest.pdftext import extract_pdf_text

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = BytesIO()
    writer.write(buf)
    data = buf.getvalue()
    text = extract_pdf_text(
        data,
        vision=lambda _raw: "主张必须挂证据才能进入已确认层。",
    )
    assert "主张必须挂证据" in text
    assert "编造的新知识" not in text

