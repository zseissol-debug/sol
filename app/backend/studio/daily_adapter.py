"""接 daily-newsletter（MIT，固定版本）：检查环境、生成今日日报、读回产出。

引擎由 scripts/setup.sh 克隆到 app/engines/daily-newsletter，配置写在它自己的 .env。
数据根目录（PARKIO_HOME）指到 app/data/park-io，避免写进 ~/park-io。
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config
from .models import NewsIssue
from .parsers.newsletter import parse_issue_markdown

LogFn = Callable[[str], None]


def engine_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PARKIO_HOME"] = str(config.PARKIO_HOME)
    return env


def daily_output_path(day: datetime | None = None) -> Path:
    day = day or datetime.now()
    return config.PARKIO_HOME / "006_ai daily newsletter" / f"{day:%y-%m-%d}.md"


def status() -> dict:
    engine = config.DAILY_ENGINE_DIR
    installed = (engine / "run-daily.sh").is_file()
    info = {
        "installed": installed,
        "configured": (engine / ".env").is_file(),
        "has_venv": (engine / ".venv" / "bin" / "python").is_file(),
        "doctor_ok": None,
        "doctor_output": "",
        "fix": "",
    }
    if not installed:
        info["fix"] = "运行 scripts/setup.sh 克隆日报引擎"
        return info
    if not info["configured"]:
        info["fix"] = f"复制 {engine}/.env.example 为 .env，至少填一个 AI（DeepSeek key，或已登录的 claude / codex 命令）"
    # 没配置也照跑 doctor：它会逐项说清缺什么（AI、各来源的登录态……）
    python = engine / ".venv" / "bin" / "python"
    try:
        proc = subprocess.run(
            [str(python) if python.is_file() else "python3", "doctor.py"],
            cwd=engine, env=engine_env(), capture_output=True, text=True, timeout=60,
        )
        info["doctor_ok"] = proc.returncode == 0
        info["doctor_output"] = (proc.stdout + proc.stderr).strip()[-4000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        info["doctor_ok"] = False
        info["doctor_output"] = f"doctor.py 运行失败：{exc}"
    return info


def generate(log: LogFn, *, runner: Callable[..., subprocess.Popen] = subprocess.Popen) -> NewsIssue:
    """跑 run-daily.sh（抓取 → AI 写日报，可能要十几分钟到半小时），读回今天的 Markdown。"""
    engine = config.DAILY_ENGINE_DIR
    if not (engine / "run-daily.sh").is_file():
        raise RuntimeError("日报引擎还没安装：运行 scripts/setup.sh")
    if not (engine / ".env").is_file():
        raise RuntimeError("日报引擎还没配置：先把 .env.example 复制成 .env 并填入 AI 设置")
    proc = runner(
        ["bash", "run-daily.sh"], cwd=engine, env=engine_env(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        log(line.rstrip())
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"日报生成失败（退出码 {code}），详见任务日志")
    path = daily_output_path()
    if not path.is_file():
        raise RuntimeError(f"没找到今天的日报文件：{path}")
    return issue_from_file(path)


def issue_from_file(path: Path) -> NewsIssue:
    m = re.match(r"(\d{2})-(\d{2})-(\d{2})\.md$", path.name)
    if not m:
        raise ValueError(f"日报文件名应为 YY-MM-DD.md：{path.name}")
    issue_id = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return parse_issue_markdown(path.read_text(encoding="utf-8"), issue_id=issue_id, source="local")
