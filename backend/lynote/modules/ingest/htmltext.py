"""Turn HTML into locatable plain text. Ingest only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from html import unescape


_SKIP = {"script", "style", "noscript", "template"}
_BLOCK = {
    "p",
    "div",
    "br",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "tr",
    "section",
    "article",
    "blockquote",
}


@dataclass(frozen=True)
class HtmlText:
    title: str
    text: str


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if name == "title":
            self._in_title = True
        if name in _BLOCK:
            self.body_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in _SKIP and self._skip:
            self._skip -= 1
            return
        if name == "title":
            self._in_title = False
        if name in _BLOCK and not self._skip:
            self.body_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        self.body_parts.append(data)


def html_to_text(raw: str) -> HtmlText:
    parser = _Extractor()
    parser.feed(unescape(raw))
    parser.close()
    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
    text = re.sub(r"[ \t]+", " ", "".join(parser.body_parts))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return HtmlText(title=title, text=text)
