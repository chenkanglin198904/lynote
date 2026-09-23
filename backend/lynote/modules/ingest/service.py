"""Ingest turns raw input into Source. Must not extract claims or write the graph."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from lynote.config import settings
from lynote.contracts.models import IngestSourceRequest, Source, SourceKind
from lynote.modules.graph.ids import new_id
from lynote.modules.ingest.avtext import transcribe_audio, transcribe_video
from lynote.modules.ingest.fetch import FetchedPage, assert_http_url, fetch_url
from lynote.modules.ingest.htmltext import html_to_text
from lynote.modules.ingest.pdftext import extract_pdf_text

Fetcher = Callable[[str], FetchedPage]

_CREDIBILITY: dict[SourceKind, float] = {
    "note": 0.75,
    "url": 0.55,
    "markdown": 0.7,
    "pdf": 0.65,
    "audio": 0.7,
    "video": 0.7,
}


class IngestService:
    def __init__(self, fetch: Fetcher | None = None) -> None:
        self._fetch = fetch or fetch_url

    def ingest(self, payload: IngestSourceRequest) -> Source:
        kind = payload.kind
        title = (payload.title or "").strip()
        text = payload.text or ""
        uri = (payload.uri or "").strip() or None

        if kind == "url" or (uri and uri.startswith(("http://", "https://")) and not text.strip()):
            if not uri:
                raise ValueError("网页入库需要 URL")
            title, text, uri, kind = self._from_url(uri, title, text, kind)
        elif kind == "pdf" and not text.strip():
            raise ValueError("PDF 请用上传接口，或先抽出正文再入库")
        elif kind == "markdown" and uri and uri.startswith(("http://", "https://")) and not text.strip():
            title, text, uri, kind = self._from_url(uri, title, text, "markdown")

        text = text.strip()
        if not text:
            raise ValueError("没有正文，无法入库")
        if not title:
            title = _fallback_title(uri, text)
        return Source(
            id=new_id("src"),
            kind=kind,
            title=title,
            uri=uri,
            text=text,
            created_at=datetime.now(timezone.utc).isoformat(),
            credibility=_CREDIBILITY.get(kind, 0.5),
        )

    def ingest_upload(self, filename: str, data: bytes, title: str = "") -> Source:
        max_upload = settings.ingest_upload_max_bytes
        if len(data) > max_upload:
            raise ValueError(f"上传文件超过 {max_upload // (1024 * 1024)}MB，拒绝入库")
        if not data:
            raise ValueError("空文件无法入库")
        name = Path(filename or "upload").name
        stem = Path(name).stem or "未命名来源"
        lower = name.lower()
        kind: SourceKind
        uri = name
        if lower.endswith(".pdf"):
            kind = "pdf"
            text = extract_pdf_text(data)
            if not text:
                raise ValueError("这份 PDF 抽不出文字（扫描件需要配置 LLM_API_KEY 才能视觉抽字）")
        elif lower.endswith((".md", ".markdown")):
            kind = "markdown"
            text = data.decode("utf-8", errors="replace")
        elif lower.endswith((".html", ".htm")):
            parsed = html_to_text(data.decode("utf-8", errors="replace"))
            kind = "url"
            text = parsed.text
            title = title.strip() or parsed.title or stem
        elif lower.endswith(".txt"):
            kind = "note"
            text = data.decode("utf-8", errors="replace")
        elif lower.endswith((".mp3", ".wav", ".m4a", ".ogg", ".webm", ".aac")):
            kind = "audio"
            text = transcribe_audio(data, name)
        elif lower.endswith((".mp4", ".mov", ".mkv")):
            kind = "video"
            text = transcribe_video(data, name)
        else:
            raise ValueError("只接受 .md / .txt / .html / .pdf / 音频 / 视频")
        return self.ingest(
            IngestSourceRequest(
                kind=kind,
                title=(title or "").strip() or stem,
                text=text,
                uri=uri,
            )
        )

    def _from_url(
        self,
        uri: str,
        title: str,
        text: str,
        kind: SourceKind,
    ) -> tuple[str, str, str, SourceKind]:
        assert_http_url(uri)
        page = self._fetch(uri)
        resolved = page.url or uri
        if page.content_type == "application/pdf" or resolved.lower().endswith(".pdf"):
            extracted = extract_pdf_text(page.data)
            if not extracted:
                raise ValueError("这份 PDF 抽不出文字（扫描件需要配置 LLM_API_KEY 才能视觉抽字）")
            return title or _fallback_title(resolved, extracted), extracted, resolved, "pdf"
        body = text.strip() or page.text
        if page.content_type in {"text/html", "application/xhtml+xml"} or (
            not page.content_type and _looks_like_html(body)
        ):
            parsed = html_to_text(body)
            body = parsed.text
            title = title or parsed.title
            kind = "url"
        elif kind == "note":
            kind = "url"
        if not body.strip():
            raise ValueError("这个链接没有可抽取的正文")
        return title, body, resolved, kind


def _looks_like_html(text: str) -> bool:
    sample = text.lstrip()[:200].lower()
    return sample.startswith("<!doctype html") or sample.startswith("<html")


def _fallback_title(uri: str | None, text: str) -> str:
    if uri:
        name = Path(url_basename(uri)).stem
        if name:
            return name
    line = next((part.strip() for part in text.splitlines() if part.strip()), "未命名来源")
    return line[:40]


def url_basename(uri: str) -> str:
    path = uri.split("?", 1)[0].rstrip("/")
    return path.rsplit("/", 1)[-1] or uri
