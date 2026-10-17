"""Park 公开的两个 RSS：AI 日报、抖音爆款拆解库。只读；原话版权归原作者，仅作本地演示与学习。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

import httpx

from .. import config
from ..models import NewsIssue, Report
from ..parsers.newsletter import parse_issue_html
from ..parsers.report import parse_report_html

HEADERS = {"User-Agent": "content-studio-local/0.1 (+personal use)"}


@dataclass
class FeedItem:
    title: str
    link: str
    published_at: str
    html: str


def fetch_feed(url: str, *, client: httpx.Client | None = None) -> list[FeedItem]:
    own = client is None
    client = client or httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_feed(resp.content)
    finally:
        if own:
            client.close()


def parse_feed(content: bytes) -> list[FeedItem]:
    root = ET.fromstring(content)
    items: list[FeedItem] = []
    for item in root.iter("item"):
        pub = item.findtext("pubDate") or ""
        try:
            published = parsedate_to_datetime(pub).isoformat(timespec="seconds")
        except (TypeError, ValueError):
            published = pub
        items.append(
            FeedItem(
                title=(item.findtext("title") or "").strip(),
                link=(item.findtext("link") or "").strip(),
                published_at=published,
                html=item.findtext("description") or "",
            )
        )
    return items


# ---------------------------------------------------------------- 日报


def issue_from_item(item: FeedItem) -> NewsIssue | None:
    m = re.search(r"/newsletter/(\d{4}-\d{2}-\d{2})", item.link)
    if not m:
        return None
    return parse_issue_html(item.html, issue_id=m.group(1), title=item.title, source="park_public", published_at=item.published_at)


# ---------------------------------------------------------------- 拆解库

_TITLE = re.compile(r"^(?:(?P<mult>[\d.,]+)×\s*·\s*)?(?P<rest>.+)$", re.S)


def report_from_item(item: FeedItem) -> Report | None:
    m = re.search(r"/teardown/(\d+)\.html", item.link)
    if not m:
        return None
    vid = m.group(1)
    rest = _TITLE.match(item.title).group("rest").strip()  # type: ignore[union-attr]
    author_m = re.search(r"作者：\s*([^<\n]+)", re.sub(r"<[^>]+>", "\n", item.html))
    author = author_m.group(1).strip() if author_m else None
    title = rest
    quoted = re.search(r"「(.+)」\s*$", rest, re.S)
    if quoted:
        title = quoted.group(1).strip()
        if not author:
            author = rest[: quoted.start()].strip() or None
    return parse_report_html(
        item.html,
        report_id=vid,
        title=title,
        author=author,
        source_url=f"https://www.douyin.com/video/{vid}",
        generated_at=item.published_at,
        source="park_public",
    )


def sync_newsletters(client: httpx.Client | None = None) -> list[NewsIssue]:
    return [i for i in (issue_from_item(x) for x in fetch_feed(config.PARK_NEWSLETTER_FEED, client=client)) if i]


def sync_teardowns(client: httpx.Client | None = None) -> list[Report]:
    return [r for r in (report_from_item(x) for x in fetch_feed(config.PARK_TEARDOWN_FEED, client=client)) if r]
