"""拆解报告解析。

三种输入归一成 models.Report：
  1. douyin-teardown 自己产出的 report.json（schema_version 2）→ from_teardown_json
  2. Park 公开库 RSS 里的 HTML                                   → parse_report_html
  3. report.md（引擎渲染的 Markdown）                            → parse_report_markdown
"""
from __future__ import annotations

import re
from typing import Any

import markdown as md_lib
from bs4 import BeautifulSoup, Tag

from ..models import Conclusion, Evidence, Opening, Report, Segment, Source

# 报告「数据」表的行名 → facts 键（与 douyin_teardown.structure.FACT_LABELS 一致）
LABEL_TO_KEY = {
    "点赞": "likes",
    "播放": "views",
    "评论": "comments",
    "转发": "shares",
    "收藏": "collects",
    "收藏/赞": "collect_per_like",
    "转发/赞": "share_per_like",
    "评论/赞": "comment_per_like",
    "赞/播放": "like_per_view",
    "该账号近期点赞中位数": "account_median_likes",
    "中位数样本条数": "account_post_count",
    "点赞是账号中位数的倍数": "multiple_of_median",
    "后台播放": "creator_view_count",
    "后台完播率": "creator_completion_rate",
    "后台 5 秒完播率": "creator_completion_rate_5s",
    "后台 2 秒跳出率": "creator_bounce_rate_2s",
    "后台平均观看秒数": "creator_avg_view_second",
    "后台封面点击率": "creator_cover_click_rate",
    "后台主页访问": "creator_homepage_visit_count",
    "后台涨粉": "creator_fan_increment",
}

_TS = r"(\d+):(\d{2})"
_RANGE = re.compile(rf"\[?{_TS}\s*[–—\-]\s*{_TS}\]?")


def _secs(minutes: str, seconds: str) -> float:
    return int(minutes) * 60 + int(seconds)


def _num(raw: str) -> float | int | None:
    text = raw.strip().replace(",", "")
    try:
        if text.endswith("%"):
            return round(float(text[:-1]) / 100, 4)
        if text.endswith("×"):
            return float(text[:-1])
        if text.endswith("秒"):
            return float(text[:-1].strip())
        value = float(text)
        return int(value) if value.is_integer() and "." not in text else value
    except ValueError:
        return None


def _evidence_from(minutes: str, seconds: str, quote: str) -> list[Evidence]:
    start = _secs(minutes, seconds)
    return [Evidence(start=start, end=start, quote=quote.strip())]


_CONCLUSION = re.compile(
    rf"^(?P<text>.*?)\s*(?:（证据：|证据：)\[{_TS}\]\s*(?P<quote>.*?)(?:）)?\s*$", re.S
)


def _conclusion(text: str) -> Conclusion:
    text = text.strip()
    match = _CONCLUSION.match(text)
    if not match:
        return Conclusion(text=text)
    return Conclusion(
        text=match.group("text").strip(),
        evidence=_evidence_from(match.group(2), match.group(3), match.group("quote")),
    )


def _table_rows(table: Tag) -> list[list[str]]:
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if cells:
            rows.append(cells)
    return rows


def _next_siblings_until(node: Tag, stop: tuple[str, ...]) -> list[Tag]:
    out = []
    for sib in node.next_siblings:
        if isinstance(sib, Tag):
            if sib.name in stop:
                break
            out.append(sib)
    return out


def _find_h2(root: Tag, title: str) -> Tag | None:
    for h in root.find_all("h2"):
        if h.get_text(strip=True) == title:
            return h
    return None


def parse_report_html(
    html: str,
    *,
    report_id: str,
    title: str,
    author: str | None,
    source_url: str | None,
    generated_at: str,
    source: Source,
) -> Report:
    root = BeautifulSoup(f"<div>{html}</div>", "html.parser").div
    assert root is not None

    # ---- 数据
    facts: dict[str, float | int | None] = {}
    h = _find_h2(root, "数据")
    table = h.find_next_sibling("table") if h else None
    if table:
        for row in _table_rows(table)[1:]:
            if len(row) >= 2 and row[0] in LABEL_TO_KEY:
                facts[LABEL_TO_KEY[row[0]]] = _num(row[1])

    # ---- 主线
    h = _find_h2(root, "主线一句话")
    quote = h.find_next_sibling("blockquote") if h else None
    thesis = _conclusion(quote.get_text("\n", strip=True)) if quote else Conclusion(text="")

    # ---- 前 N 秒（仅自己的视频）
    opening = None
    for h2 in root.find_all("h2"):
        m = re.match(r"观众平均看到的前\s*(\d+)\s*秒", h2.get_text(strip=True))
        if m:
            body = _next_siblings_until(h2, ("h2",))
            analysis = next((n.get_text(" ", strip=True) for n in body if n.name == "p"), "")
            quote_node = next((n for n in body if n.name == "blockquote"), None)
            transcript = quote_node.get_text(" ", strip=True).removeprefix("这段原文：") if quote_node else ""
            opening = Opening(seconds=float(m.group(1)), analysis=analysis, transcript=transcript)

    # ---- 分段时间轴
    segments: list[Segment] = []
    drift_seconds = drift_share = 0.0
    h = _find_h2(root, "分段时间轴")
    if h:
        for node in _next_siblings_until(h, ("h2",)):
            if node.name == "p":
                m = re.search(r"跑题合计\s*(\d+)\s*秒，占全片\s*(\d+)%", node.get_text())
                if m:
                    drift_seconds, drift_share = float(m.group(1)), int(m.group(2)) / 100
            elif node.name == "table":
                for row in _table_rows(node)[1:]:
                    rng = _RANGE.search(row[0]) if row else None
                    if not rng or len(row) < 5:
                        continue
                    label = row[1]
                    segments.append(
                        Segment(
                            index=len(segments),
                            label=label,
                            drift=(label == "跑题" or row[2] == "否"),
                            start=_secs(rng.group(1), rng.group(2)),
                            end=_secs(rng.group(3), rng.group(4)),
                            summary=row[3],
                            reason=row[4],
                        )
                    )

    # ---- 逐段原文
    h = _find_h2(root, "逐段原文")
    if h:
        current: int | None = None
        for node in _next_siblings_until(h, ("h2",)):
            if node.name == "h3":
                rng = _RANGE.search(node.get_text())
                current = None
                if rng:
                    start = _secs(rng.group(1), rng.group(2))
                    current = next((s.index for s in segments if s.start == start), None)
            elif node.name == "p" and current is not None:
                seg = segments[current]
                seg.text = (seg.text + " " + node.get_text(" ", strip=True)).strip()

    # ---- 为什么爆 / 为什么散
    def conclusions(title_: str) -> list[Conclusion]:
        head = _find_h2(root, title_)
        ul = head.find_next_sibling("ul") if head else None
        return [_conclusion(li.get_text(" ", strip=True)) for li in ul.find_all("li", recursive=False)] if ul else []

    note = ""
    h = _find_h2(root, "解释边界")
    if h:
        bq = h.find_next_sibling("blockquote")
        note = bq.get_text(" ", strip=True) if bq else ""

    duration = segments[-1].end if segments else 0.0
    return Report(
        id=report_id,
        title=title,
        author=author,
        source_url=source_url,
        generated_at=generated_at,
        duration_seconds=duration,
        facts=facts,
        thesis=thesis,
        opening=opening,
        segments=segments,
        drift_seconds=drift_seconds,
        drift_share=drift_share,
        why_boom=conclusions("为什么爆"),
        why_scatter=conclusions("为什么散"),
        hypothesis_note=note,
        source=source,
    )


def parse_report_markdown(text: str, *, source: Source = "local") -> Report:
    """report.md（引擎渲染）→ Report。标题、作者、链接、生成时间取自文件头。"""
    html = md_lib.markdown(text, extensions=["tables", "sane_lists"])
    head = BeautifulSoup(f"<div>{html}</div>", "html.parser")
    h1 = head.find("h1")
    title = h1.get_text(strip=True) if h1 else "未命名视频"
    meta = {k: v for k, v in re.findall(r"-\s*(作者|链接|生成时间)：(.+)", text)}
    link = meta.get("链接", "").strip() or None
    vid = re.search(r"/video/(\d+)", link or "")
    return parse_report_html(
        html,
        report_id=vid.group(1) if vid else "unknown",
        title=title,
        author=(meta.get("作者") or "").strip() or None,
        source_url=link,
        generated_at=(meta.get("生成时间") or "").strip().strip("`"),
        source=source,
    )


def from_teardown_json(data: dict[str, Any], *, source: Source = "local") -> Report:
    """douyin-teardown 的 report.json（schema_version 2）→ Report。"""

    def evidence(items: list[dict]) -> list[Evidence]:
        return [Evidence(start=float(e.get("start", 0)), end=float(e.get("end", 0)), quote=str(e.get("quote", ""))) for e in items or []]

    def conclusion(item: dict) -> Conclusion:
        return Conclusion(text=str(item.get("text", "")), evidence=evidence(item.get("evidence", [])))

    opening = data.get("opening")
    drift = data.get("drift") or {}
    segments = [
        Segment(
            index=int(s.get("index", i)),
            label=str(s["label"]),
            drift=bool(s.get("drift", s["label"] == "跑题")),
            start=float(s["start"]),
            end=float(s["end"]),
            summary=str(s.get("summary", "")),
            reason=str(s.get("reason", "")),
            text=str(s.get("text", "")),
        )
        for i, s in enumerate(data.get("segments", []))
    ]
    duration = (data.get("transcript") or {}).get("duration_seconds") or (segments[-1].end if segments else 0)
    return Report(
        id=str(data["content_id"]),
        title=str(data.get("title") or "未命名视频"),
        author=data.get("author"),
        source_url=data.get("source_url"),
        generated_at=str(data.get("generated_at", "")),
        duration_seconds=float(duration),
        facts={k: v for k, v in (data.get("facts") or {}).items() if isinstance(v, (int, float)) or v is None},
        thesis=conclusion(data.get("thesis") or {"text": ""}),
        opening=Opening(seconds=float(opening["seconds"]), analysis=str(opening.get("analysis", "")), transcript=str(opening.get("transcript", ""))) if opening else None,
        segments=segments,
        drift_seconds=float(drift.get("seconds", 0)),
        drift_share=float(drift.get("share", 0)),
        why_boom=[conclusion(i) for i in data.get("why_boom", [])],
        why_scatter=[conclusion(i) for i in data.get("why_scatter", [])],
        hypothesis_note=str(data.get("hypothesis_note", "")),
        source=source,
    )
