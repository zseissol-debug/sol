"""日报适配层：用假引擎目录验证，不依赖网络和 AI。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from studio import config, daily_adapter

MD = """# AI Daily Newsletter — 2026-10-16

## 快讯
### 底层工具
- **Claude Code Release** | [v2.1.170](https://github.com/x/y)
  版本更新说明。

## 深读
### [一篇深读](https://example.com/a)
深读正文。
"""


@pytest.fixture()
def fake_engine(tmp_path, monkeypatch):
    engine = tmp_path / "daily-newsletter"
    engine.mkdir()
    (engine / "run-daily.sh").write_text("#!/bin/bash\n")
    (engine / "doctor.py").write_text("print('✗ 没有可用的 AI')\nraise SystemExit(1)\n")
    monkeypatch.setattr(config, "DAILY_ENGINE_DIR", engine)
    monkeypatch.setattr(config, "PARKIO_HOME", tmp_path / "park-io")
    return engine


def test_status_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DAILY_ENGINE_DIR", tmp_path / "nope")
    s = daily_adapter.status()
    assert s["installed"] is False and "setup.sh" in s["fix"]


def test_status_runs_doctor_even_without_env(fake_engine):
    s = daily_adapter.status()
    assert s["installed"] and not s["configured"]
    assert s["doctor_ok"] is False
    assert "没有可用的 AI" in s["doctor_output"], "没配置时也要把 doctor 的结论给用户看"
    assert ".env" in s["fix"]


def test_engine_env_points_data_into_project(fake_engine):
    assert daily_adapter.engine_env()["PARKIO_HOME"] == str(config.PARKIO_HOME)


def test_generate_requires_env_file(fake_engine):
    with pytest.raises(RuntimeError, match="还没配置"):
        daily_adapter.generate(lambda _l: None)


def _runner_writing(md: str | None, code: int):
    def run(cmd, **kw):
        if md is not None:
            out = daily_adapter.daily_output_path()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md, encoding="utf-8")

        class P:
            stdout = iter(["[11:00] 1/3 检查环境\n", "[11:05] 2/3 抓取来源\n"])

            def wait(self):
                return code

        return P()

    return run


def test_generate_reads_back_output(fake_engine):
    (fake_engine / ".env").write_text("PARKIO_LLM_PROVIDER=deepseek\n")
    lines: list[str] = []
    issue = daily_adapter.generate(lines.append, runner=_runner_writing(MD, 0))
    assert lines == ["[11:00] 1/3 检查环境", "[11:05] 2/3 抓取来源"]
    assert issue.source == "local" and issue.brief_count == 1
    assert issue.sections[0].groups[0].items[0].url == "https://github.com/x/y"


def test_generate_failure_and_missing_output(fake_engine):
    (fake_engine / ".env").write_text("x=1\n")
    with pytest.raises(RuntimeError, match="退出码 1"):
        daily_adapter.generate(lambda _l: None, runner=_runner_writing(None, 1))
    with pytest.raises(RuntimeError, match="没找到今天的日报"):
        daily_adapter.generate(lambda _l: None, runner=_runner_writing(None, 0))


def test_issue_from_file_name_parsing(tmp_path):
    f = tmp_path / "26-10-16.md"
    f.write_text(MD, encoding="utf-8")
    assert daily_adapter.issue_from_file(f).id == "2026-10-16"
    bad = tmp_path / "today.md"
    bad.write_text(MD, encoding="utf-8")
    with pytest.raises(ValueError):
        daily_adapter.issue_from_file(bad)
