"""Fetch remote documents for ingest. Local-first: only http/https."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from lynote.config import settings


@dataclass(frozen=True)
class FetchedPage:
    url: str
    content_type: str
    data: bytes
    text: str


def assert_http_url(uri: str) -> str:
    url = uri.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("只允许 http/https 链接，不能用 file 或其他协议")
    return url


def fetch_url(uri: str, *, client: httpx.Client | None = None) -> FetchedPage:
    url = assert_http_url(uri)
    headers = {"User-Agent": settings.ingest_user_agent}
    own_client = client is None
    http = client or httpx.Client(
        timeout=settings.ingest_fetch_timeout,
        follow_redirects=True,
        headers=headers,
    )
    try:
        response = http.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"无法抓取链接：{exc}") from exc
    finally:
        if own_client:
            http.close()
    data = response.content
    max_bytes = settings.ingest_fetch_max_bytes
    if len(data) > max_bytes:
        raise ValueError(f"远程文件超过 {max_bytes // (1024 * 1024)}MB，拒绝入库")
    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    text = ""
    if content_type.startswith("text/") or content_type in {"application/json", "application/xml"}:
        text = data.decode(response.encoding or "utf-8", errors="replace")
    elif not content_type:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
    return FetchedPage(url=str(response.url), content_type=content_type, data=data, text=text)
