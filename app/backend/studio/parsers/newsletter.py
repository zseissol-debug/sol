"""AI 日报解析：Park 公开 RSS 的 HTML 与本地引擎产出的 Markdown，统一成 NewsIssue。"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

import markdown as md_lib
from bs4 import BeautifulSoup, Tag

from ..models import NewsGroup, NewsIssue, NewsItem, NewsSection, Source

KIND_BY_TITLE = (("快讯", "brief"), ("深读", "deep"), ("产品雷达", "radar"))


def _kind(title: str) -> str:
    for prefix, kind in KIND_BY_TITLE:
        if title.startswith(prefix):
            return kind
    return "other"


def _item_id(kind: str, url: str | None, title: str) -> str:
    digest = hashlib.sha1(f"{url or ''}|{title}".encode("utf-8")).hexdigest()[:10]
    return f"{kind}-{digest}"


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _parse_li(li: Tag, kind: str) -> NewsItem:
    link = li.find("a")
    strong = li.find("strong")
    source = strong.get_text(strip=True) if strong else None
    title = link.get_text(strip=True) if link else ""
    url = link.get("href") if link else None

    rest = BeautifulSoup(str(li), "html.parser")
    for tag in rest.find_all(["strong", "a"]):
        tag.decompose()
    summary = _clean(rest.get_text("\n").lstrip(" |\n"))
    if not title:  # 产品雷达等没有链接的条目：「名称：说明」
        whole = li.get_text(" ", strip=True)
        head, sep, tail = whole.partition("：")
        title, summary = (head, tail.strip()) if sep and len(head) <= 40 else (whole, "")
    return NewsItem(id=_item_id(kind, url, title), title=title, url=url, source=source, summary=summary)


def _items_from(lists: Iterable[Tag], kind: str) -> list[NewsItem]:
    return [_parse_li(li, kind) for ul in lists for li in ul.find_all("li", recursive=False)]


def _build_section(title: str, nodes: list[Tag]) -> NewsSection:
    kind = _kind(title)
    section = NewsSection(kind=kind, title=title)  # type: ignore[arg-type]
    texts: list[str] = []

    if kind == "deep":
        current: NewsItem | None = None
        paragraphs: list[str] = []

        def flush() -> None:
            nonlocal current, paragraphs
            if current is not None:
                current.summary = "\n\n".join(paragraphs).strip()
                if not section.groups:
                    section.groups.append(NewsGroup())
                section.groups[0].items.append(current)
            current, paragraphs = None, []

        for node in nodes:
            if node.name == "h3":
                flush()
                link = node.find("a")
                name = node.get_text(strip=True)
                url = link.get("href") if link else None
                current = NewsItem(id=_item_id("deep", url, name), title=name, url=url)
            elif node.name == "p" and current is not None:
                paragraphs.append(node.get_text("\n", strip=True))
        flush()
        return section

    group: NewsGroup | None = None
    for node in nodes:
        if node.name == "h3":
            group = NewsGroup(name=node.get_text(strip=True))
            section.groups.append(group)
        elif node.name in ("ul", "ol"):
            if group is None:
                group = NewsGroup()
                section.groups.append(group)
            group.items.extend(_items_from([node], kind))
        elif node.name in ("p", "blockquote"):
            texts.append(node.get_text("\n", strip=True))
    section.text = _clean("\n\n".join(texts)) or None
    return section


def parse_issue_html(html: str, *, issue_id: str, title: str, source: Source, published_at: str | None = None) -> NewsIssue:
    root = BeautifulSoup(f"<div>{html}</div>", "html.parser").div
    assert root is not None
    sections: list[NewsSection] = []
    title_nodes: list[tuple[str, list[Tag]]] = []
    for node in root.children:
        if not isinstance(node, Tag) or node.name == "h1":
            continue
        if node.name == "h2":
            title_nodes.append((node.get_text(strip=True), []))
        elif title_nodes:
            title_nodes[-1][1].append(node)
    for name, nodes in title_nodes:
        sections.append(_build_section(name, nodes))
    brief_count = sum(len(g.items) for s in sections if s.kind == "brief" for g in s.groups)
    return NewsIssue(id=issue_id, title=title, published_at=published_at, source=source, sections=sections, brief_count=brief_count)


def parse_issue_markdown(text: str, *, issue_id: str, source: Source = "local") -> NewsIssue:
    html = md_lib.markdown(text, extensions=["extra", "sane_lists"])
    head = re.search(r"(?m)^#\s+(.+)$", text)
    title = head.group(1).strip() if head else f"AI 日报 · {issue_id}"
    return parse_issue_html(html, issue_id=issue_id, title=title, source=source)
