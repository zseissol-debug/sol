"""用真实的 douyin-teardown 流水线（只把下载 / 转写 / AI 三步换成假的）产出真正的 report.json，
再验证我们的适配层能完整读回。引擎没装就跳过。"""
from __future__ import annotations

import functools
import json
from pathlib import Path

import pytest

pipeline = pytest.importorskip("douyin_teardown.pipeline")

from studio import teardown_adapter as ta  # noqa: E402

VIDEO_ID = "7604889380867588283"
URL = f"https://www.douyin.com/video/{VIDEO_ID}"

LINES = [  # (start, end, text)  共 3 分钟，每 15 秒一句
    (i * 15.0, i * 15.0 + 14.0, f"第{i}句原话：这是口播的内容 {i}") for i in range(12)
]


def fake_download(url, cookie_path, downloads_dir: Path) -> Path:
    d = downloads_dir / "douyin" / VIDEO_ID
    (d / "media").mkdir(parents=True)
    (d / "media" / "video.mp4").write_bytes(b"x" * 2048)
    (d / "content_item.json").write_text(json.dumps({
        "content_id": VIDEO_ID, "platform": "douyin", "title": "错位的爱，才最痛苦", "author_name": "一勾工作号",
        "likes": 166489, "comments": 9967, "shares": 60575, "collects": 26939,
    }, ensure_ascii=False))
    return d


def fake_extract(content_dir: Path, model: str) -> Path:
    (content_dir / "transcript.json").write_text(json.dumps({
        "language": "zh", "segments": [{"start": s, "end": e, "text": t} for s, e, t in LINES],
    }, ensure_ascii=False))
    return content_dir


def fake_judge(_prompt: str) -> dict:
    return {
        "thesis": {"text": "父母给安全感，子女要被看见，这种错位最痛苦", "evidence_start": 30},
        "segments": [
            {"start": 0, "end": 45, "label": "钩子", "summary": "抛出主题", "serves_thesis": True, "reason": "建立问题"},
            {"start": 45, "end": 120, "label": "论点", "summary": "展开错位", "serves_thesis": True, "reason": "主线论据"},
            {"start": 120, "end": 150, "label": "跑题", "summary": "推荐别人", "serves_thesis": False, "reason": "删掉不影响主线"},
            {"start": 150, "end": 179, "label": "收束", "summary": "回到主题", "serves_thesis": True, "reason": "收尾"},
        ],
        "why_boom": [{"text": "点赞 323.9× 于账号中位数，说明观众把它当可转发的表达", "evidence_start": 30}],
        "why_scatter": [{"text": "中段离题推荐他人，打断主线", "evidence_start": 125}],
        "opening": None,
    }


def test_real_pipeline_output_is_read_back_by_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("TEARDOWN_DATA_DIR", str(tmp_path / "td"))
    monkeypatch.setenv("TEARDOWN_COOKIES", str(tmp_path / "cookies.json"))
    stages: list[str] = []
    process = functools.partial(
        pipeline.process_url,
        download_fn=fake_download, extract_fn=fake_extract, judge_fn=fake_judge,
        baseline_fn=lambda *_a: {"post_count": 168, "median_likes": 514, "excludes_pinned": True},
    )
    report = ta.run_teardown(URL, stages.append, process_fn=process)

    assert stages == ["downloading", "transcribing", "analyzing"]
    assert report.source == "local" and report.id == VIDEO_ID
    assert report.author == "一勾工作号" and report.title == "错位的爱，才最痛苦"
    assert report.source_url == URL
    # 倍数由程序算，不是 AI：166489 / 514 = 323.9
    assert report.facts["multiple_of_median"] == 323.9
    assert report.facts["share_per_like"] == pytest.approx(0.364, abs=0.001)
    # 分段与逐段原文由程序按秒数从转写稿切
    assert [s.label for s in report.segments] == ["钩子", "论点", "跑题", "收束"]
    first = report.segments[0].text  # 0–45 秒：第 0、1、2 句；第 3 句从 45 秒开始，归下一段
    assert "第0句原话" in first and "第2句原话" in first and "第3句原话" not in first
    assert "第3句原话" in report.segments[1].text
    assert report.segments[2].drift and not report.segments[0].drift
    # 跑题秒数由程序累加：30 秒 / 179 秒
    assert report.drift_seconds == 30
    assert report.drift_share == pytest.approx(30 / 179, abs=0.01)
    # 证据原话由程序按 evidence_start 取，AI 改不了
    assert report.thesis.evidence[0].quote.startswith("第2句原话")
    assert report.why_boom[0].evidence and report.why_scatter[0].evidence
    assert report.hypothesis_note.startswith("结构标签")
    assert report.duration_seconds == pytest.approx(179, abs=1)

    # 引擎按约定在拆完后删掉视频，只留文字
    d = tmp_path / "td" / "downloads" / "douyin" / VIDEO_ID
    assert not (d / "media").exists() and (d / "transcript.json").is_file()
    # 报告文件落在 reports/<id>/report.json
    assert (tmp_path / "td" / "reports" / VIDEO_ID / "report.json").is_file()


def test_failure_from_engine_surfaces_as_teardown_error(tmp_path, monkeypatch):
    monkeypatch.setenv("TEARDOWN_DATA_DIR", str(tmp_path / "td"))

    def boom(*_a, **_k):
        raise RuntimeError("cookies 缺失")

    process = functools.partial(pipeline.process_url, download_fn=boom)
    with pytest.raises(ta.TeardownError, match="cookies 缺失"):
        ta.run_teardown(URL, lambda _s: None, process_fn=process)


def test_environment_check_reports_real_gaps(monkeypatch, tmp_path):
    monkeypatch.setenv("TEARDOWN_COOKIES", str(tmp_path / "nope.json"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TEARDOWN_DEEPSEEK_KEY", raising=False)
    monkeypatch.setenv("TEARDOWN_AI", "deepseek")
    checks = {c["key"]: c for c in ta.check_environment()}
    assert checks["python"]["ok"]
    assert checks["cookies"]["ok"] is False and "cookies" in checks["cookies"]["fix"]
    assert checks["ai"]["ok"] is False and "app/.env" in checks["ai"]["fix"]
