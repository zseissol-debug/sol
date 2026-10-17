"""解析器测试：用真实的 Park 公开数据（fixtures）验证，而不是自己编的样例。"""
from __future__ import annotations

from pathlib import Path

import pytest

from studio.parsers.newsletter import parse_issue_markdown
from studio.parsers.report import parse_report_markdown
from studio.sources import park_public

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def teardown_items():
    return park_public.parse_feed((FIX / "teardown-feed.xml").read_bytes())


@pytest.fixture(scope="module")
def newsletter_items():
    return park_public.parse_feed((FIX / "newsletter-feed.xml").read_bytes())


# ------------------------------------------------------------- 拆解报告


def test_all_public_reports_parse_with_core_fields(teardown_items):
    reports = [park_public.report_from_item(i) for i in teardown_items]
    assert len(reports) == len(teardown_items) >= 40
    for r in reports:
        assert r is not None
        assert r.id.isdigit()
        assert r.title and r.thesis.text, r.id
        assert len(r.segments) >= 2, f"{r.id} 分段太少"
        assert r.why_boom, f"{r.id} 缺为什么爆"
        assert r.hypothesis_note.startswith("结构标签")


def test_segments_are_contiguous_and_have_text(teardown_items):
    r = park_public.report_from_item(teardown_items[0])
    assert r.segments[0].start == 0
    for a, b in zip(r.segments, r.segments[1:]):
        assert a.end <= b.start + 1, (a, b)
    assert all(s.text for s in r.segments), "每段都应有逐段原文"
    assert r.duration_seconds == r.segments[-1].end


def test_first_report_known_values(teardown_items):
    """第一条是一勾工作号「影响客单价的三个核心要素」，数字取自当时的 RSS。"""
    r = park_public.report_from_item(teardown_items[0])
    assert r.author == "一勾工作号"
    assert r.title == "影响客单价的三个核心要素"
    assert r.facts["likes"] == 1801
    assert r.facts["multiple_of_median"] == 3.4
    assert r.facts["collect_per_like"] == pytest.approx(0.567)
    assert r.facts["account_median_likes"] == 536
    assert r.drift_seconds == 40 and r.drift_share == pytest.approx(0.23)
    assert any(s.drift for s in r.segments)
    assert r.thesis.evidence and r.thesis.evidence[0].start == 168  # [02:48]
    assert all(c.evidence for c in r.why_boom)
    assert r.source_url.endswith(r.id)


def test_drift_flag_matches_label_and_total(teardown_items):
    """跑题标签 ⇔ 不服务主线；逐段跑题秒数之和应与报告写的「跑题合计」一致（取整误差 ≤ 2 秒）。"""
    for item in teardown_items:
        r = park_public.report_from_item(item)
        for s in r.segments:
            assert s.drift == (s.label == "跑题"), (r.id, s)
        summed = sum(s.end - s.start for s in r.segments if s.drift)
        assert abs(summed - r.drift_seconds) <= 2, (r.id, summed, r.drift_seconds)


def test_markdown_example_from_engine_repo():
    """引擎仓库自带的样例（点赞 323.9 倍）走 Markdown 路径。"""
    r = parse_report_markdown((FIX / "example-report.md").read_text(encoding="utf-8"), source="local")
    assert r.id == "7604889380867588283"
    assert r.title.startswith("错位的爱")
    assert r.author == "一勾工作号"
    assert r.facts["likes"] == 166489
    assert r.facts["multiple_of_median"] == 323.9
    assert r.facts["account_post_count"] == 168
    assert r.segments and r.segments[0].label == "钩子"
    assert r.why_boom and r.why_scatter


# ------------------------------------------------------------- 日报


def test_public_newsletters_parse(newsletter_items):
    issues = [park_public.issue_from_item(i) for i in newsletter_items]
    assert all(issues) and len(issues) >= 20
    ids = [i.id for i in issues]
    assert len(set(ids)) == len(ids)
    for issue in issues:
        kinds = [s.kind for s in issue.sections]
        assert "brief" in kinds, issue.id
        assert issue.brief_count > 0


def test_latest_newsletter_structure(newsletter_items):
    issue = park_public.issue_from_item(newsletter_items[0])
    assert issue.id == "2026-10-16"
    brief = next(s for s in issue.sections if s.kind == "brief")
    assert [g.name for g in brief.groups][:3] == ["底层工具", "工作流", "内容"]
    first = brief.groups[0].items[0]
    assert first.title and first.url and first.source and first.summary
    assert "|" not in first.summary[:3]

    deep = next(s for s in issue.sections if s.kind == "deep")
    deep_items = deep.groups[0].items
    assert deep_items and all(i.url and i.summary for i in deep_items)

    radar = next(s for s in issue.sections if s.kind == "radar")
    products = radar.groups[0].items
    assert products and products[0].summary, "产品雷达应拆成「名称：说明」"


def test_item_ids_unique_within_issue(newsletter_items):
    issue = park_public.issue_from_item(newsletter_items[0])
    ids = [i.id for s in issue.sections for g in s.groups for i in g.items]
    assert len(ids) == len(set(ids))


def test_local_markdown_roundtrip():
    """引擎本地产出的 Markdown（README 示例格式）。"""
    text = """# AI Daily Newsletter — 2026-06-10

## 快讯
### 底层工具
- **Claude Code Release** | [Claude Code Release：v2.1.170](https://github.com/x/y)
  版本更新说明，适合快速知道工具变化。

### 内容
- **X / Yenita_Su** | [小红书创作窗口解析](https://x.com/a/b)
  平台扶持方向变化。

## 深读
### [Claude Code 官方循环工程入门指南](https://example.com)
文章级判断与可迁移启发。

## 产品雷达
### Top Three Products to Build Today

1. 销售通话复盘助手：自动找出客户异议和下一步动作。
"""
    issue = parse_issue_markdown(text, issue_id="2026-06-10")
    assert issue.title.startswith("AI Daily Newsletter")
    assert issue.brief_count == 2
    brief = issue.sections[0]
    assert brief.groups[0].items[0].source == "Claude Code Release"
    assert brief.groups[0].items[0].url == "https://github.com/x/y"
    deep = issue.sections[1]
    assert deep.groups[0].items[0].summary == "文章级判断与可迁移启发。"
    radar = issue.sections[2]
    assert radar.groups[0].items[0].title == "销售通话复盘助手"
