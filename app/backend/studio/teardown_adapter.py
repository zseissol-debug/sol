"""接 douyin-teardown（MIT，固定版本）。

原则（来自原仓库）：
- 抖音 cookies 由用户自己导出，放在 ~/.douyin-teardown/cookies.json，不进本项目；
- 抖音弹验证页就停，不绕过；
- AI 没登录 / 没 key，说清楚去哪配，不空转重试；
- 一次只拆一条，避免频繁用你的登录请求。
"""
from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from . import config
from .models import Report
from .parsers.report import from_teardown_json

StageFn = Callable[[str], None]
ProcessFn = Callable[..., dict]


class TeardownError(RuntimeError):
    pass


def validate_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in config.DOUYIN_HOSTS):
        raise TeardownError("目前只支持抖音链接（douyin.com / v.douyin.com）")
    return parsed.geturl()


def _load_env() -> None:
    """与 teardown 命令行一致：~/.douyin-teardown/.env，再加本项目的 app/.env；真实环境变量优先。"""
    from douyin_teardown import cli

    cli.load_env_file(cli.HOME / ".env")
    cli.load_env_file(config.APP_DIR / ".env")


def check_environment() -> list[dict]:
    """与 `teardown doctor` 同口径，但返回结构化结果给页面用。"""
    results: list[dict] = []

    def add(key: str, label: str, ok: bool, fix: str = "") -> None:
        results.append({"key": key, "label": label, "ok": ok, "fix": "" if ok else fix})

    add("python", f"Python {platform.python_version()}", sys.version_info >= (3, 11), "需要 Python 3.11 或更新")
    add("ffmpeg", "ffmpeg / ffprobe", bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), "brew install ffmpeg")

    mlx = importlib.util.find_spec("mlx_whisper") is not None
    faster = importlib.util.find_spec("faster_whisper") is not None
    apple = sys.platform == "darwin" and platform.machine() == "arm64"
    engine = "mlx-whisper（Apple 芯片 GPU）" if mlx and apple else "faster-whisper（CPU）" if faster else ""
    add("whisper", f"转文字：{engine or '没装'}", bool(engine), "运行 scripts/setup.sh --full 安装转写依赖")

    try:
        from douyin_teardown import ai, cli
        from douyin_teardown.cookies import CookieFileError, load_cookie_file

        _load_env()
        path = cli.cookie_path()
        try:
            load_cookie_file(path)
            cookie_ok, cookie_fix = True, ""
        except CookieFileError as exc:
            cookie_ok, cookie_fix = False, f"{exc}。登录 douyin.com 后导出 cookies 存成 {path}（格式见引擎仓库 cookies.json.example），再 chmod 600"
        add("cookies", f"抖音 cookies：{path}", cookie_ok, cookie_fix)

        import os

        name = (os.environ.get("TEARDOWN_AI") or ai.DEFAULT_PROVIDER).strip().lower()
        if name in ("codex", "claude"):
            ai_ok = bool(shutil.which(os.environ.get(f"TEARDOWN_{name.upper()}_BIN") or name))
        elif name == "deepseek":
            ai_ok = bool(os.environ.get("TEARDOWN_DEEPSEEK_KEY"))
        elif name == "anthropic":
            ai_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
        else:
            ai_ok = False
        fix = ai.login_hint(name) if name in ai.PROVIDERS else f"TEARDOWN_AI 只能是 {' / '.join(ai.PROVIDERS)}"
        add("ai", f"AI：{name}", ai_ok, f"{fix}（把 TEARDOWN_AI 和对应 key 写进 app/.env）")
    except ImportError:
        add("engine", "拆解引擎 douyin-teardown", False, "运行 scripts/setup.sh 安装")
    return results


def run_teardown(url: str, on_stage: StageFn, *, process_fn: ProcessFn | None = None) -> Report:
    """下载 → 转文字 → 算倍数 → AI 拆结构，返回归一后的 Report。process_fn 供测试注入。"""
    url = validate_url(url)
    try:
        from douyin_teardown import cli, pipeline
        from douyin_teardown.structure import load_glossary
    except ImportError as exc:
        raise TeardownError("拆解引擎 douyin-teardown 还没安装：先运行 scripts/setup.sh（本地转写再加 --full）") from exc

    _load_env()
    data_dir = pipeline._secure_dir(cli.data_dir())  # noqa: SLF001 - 与 run_pipeline 保持一致的目录权限
    downloads_dir = pipeline._secure_dir(data_dir / "downloads")  # noqa: SLF001
    glossary = load_glossary(pipeline.DEFAULT_GLOSSARY_PATH)
    process = process_fn or pipeline.process_url
    try:
        paths = process(
            url,
            cookie_path=cli.cookie_path(),
            data_dir=data_dir,
            downloads_dir=downloads_dir,
            glossary=glossary,
            on_stage=on_stage,
        )
    except Exception as exc:  # noqa: BLE001
        raise TeardownError(str(exc)) from exc
    data = json.loads(Path(paths["report_json"]).read_text(encoding="utf-8"))
    return from_teardown_json(data, source="local")
