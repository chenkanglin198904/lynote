"""Optional web search for classification hints. Never writes the graph.

Results are snippets + URLs. They are not claims, concepts, or a taxonomy.
Disabled unless SEARCH_BACKEND is set. Failures return empty, ingest still works.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from lynote.config import settings

SearchFn = Callable[[str, int], list["SearchHit"]]


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str


def search_web(query: str, limit: int = 4, *, search: SearchFn | None = None) -> list[SearchHit]:
    needle = " ".join(query.split())[:120]
    if not needle or limit <= 0:
        return []
    fn = search or _default_search
    try:
        hits = fn(needle, limit)
    except (ValueError, OSError, httpx.HTTPError, TypeError):
        return []
    cleaned: list[SearchHit] = []
    seen: set[str] = set()
    for hit in hits:
        url = _public_http_url(hit.url)
        if not url or url in seen:
            continue
        seen.add(url)
        title = (hit.title or url).strip()[:120]
        snippet = (hit.snippet or "").strip()[:280]
        cleaned.append(SearchHit(title=title, url=url, snippet=snippet))
        if len(cleaned) >= limit:
            break
    return cleaned


def is_configured() -> bool:
    backend = settings.search_backend.strip().lower()
    if backend in {"", "off", "none", "memory"}:
        return False
    return bool(settings.search_base_url.strip())


def _default_search(query: str, limit: int) -> list[SearchHit]:
    if not is_configured():
        return []
    return _http_search(query, limit)


def _http_search(query: str, limit: int) -> list[SearchHit]:
    endpoint = settings.search_base_url.strip()
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []
    headers = {"User-Agent": settings.ingest_user_agent, "Accept": "application/json"}
    key = settings.search_api_key.strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"query": query, "q": query, "max_results": limit, "limit": limit}
    if key:
        body["api_key"] = key
    timeout = max(3.0, min(settings.search_timeout, 20.0))
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        method = settings.search_method.strip().upper() or "POST"
        if method == "GET":
            response = client.get(endpoint, params={"q": query, "query": query, "limit": limit})
        else:
            response = client.post(endpoint, json=body)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        return []
    return _parse_hits(payload, limit)


def _parse_hits(payload: dict[str, Any], limit: int) -> list[SearchHit]:
    raw = payload.get("results")
    if not isinstance(raw, list):
        web = payload.get("web")
        raw = web.get("results") if isinstance(web, dict) else payload.get("data")
    if not isinstance(raw, list):
        return []
    hits: list[SearchHit] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("link") or "").strip()
        title = str(item.get("title") or item.get("name") or "").strip()
        snippet = str(
            item.get("snippet")
            or item.get("content")
            or item.get("description")
            or item.get("body")
            or ""
        ).strip()
        if not url:
            continue
        hits.append(SearchHit(title=title or url, url=url, snippet=snippet))
        if len(hits) >= limit:
            break
    return hits


def _public_http_url(uri: str) -> str:
    url = (uri or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return ""
    return url
