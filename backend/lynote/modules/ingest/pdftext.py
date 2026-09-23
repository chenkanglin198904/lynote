"""PDF text extraction. Ingest only — does not write the graph.

Digital text first. Empty pages may go through vision transcription when an LLM key exists.
Vision must copy visible glyphs; it must not invent claims.
"""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO

from lynote.llm.client import LlmError, complete_vision_text, is_configured

_MIN_DIGITAL = 40
_MAX_PAGES = 8
VisionFn = Callable[[bytes], str]


def extract_pdf_text(data: bytes, *, vision: VisionFn | None = None) -> str:
    digital = _pypdf_text(data)
    if len(digital.strip()) >= _MIN_DIGITAL:
        return digital
    extractor = vision if vision is not None else _default_vision
    try:
        visual = (extractor(data) or "").strip()
    except (LlmError, RuntimeError, ValueError):
        visual = ""
    if len(visual) > len(digital.strip()):
        return visual
    return digital


def _pypdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF ingest needs the pypdf package") from exc
    try:
        reader = PdfReader(BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
    except Exception as exc:
        raise ValueError("这份 PDF 无法读取") from exc
    return "\n\n".join(part.strip() for part in pages if part and part.strip()).strip()


def _default_vision(data: bytes) -> str:
    if not is_configured():
        return ""
    images = render_pdf_pages(data)
    if not images:
        return ""
    return complete_vision_text(images)


def render_pdf_pages(data: bytes, limit: int = _MAX_PAGES) -> list[bytes]:
    try:
        import fitz
    except ImportError:
        return []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return []
    images: list[bytes] = []
    try:
        for index, page in enumerate(doc):
            if index >= limit:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
            images.append(pix.tobytes("jpeg"))
    finally:
        doc.close()
    return images
