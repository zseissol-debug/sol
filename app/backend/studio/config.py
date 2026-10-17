"""路径与外部地址。所有运行时数据都放在 app/data 下，不往用户主目录散落（抖音 cookies 除外，见 teardown_adapter）。"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]  # .../app
DATA_DIR = Path(os.environ.get("STUDIO_DATA_DIR", APP_DIR / "data")).expanduser()
ENGINES_DIR = APP_DIR / "engines"
DAILY_ENGINE_DIR = ENGINES_DIR / "daily-newsletter"

# 日报引擎的数据根目录：指到项目自己的 data 下，避免写进 ~/park-io
PARKIO_HOME = DATA_DIR / "park-io"

# 拆解引擎的产物目录（报告 json/md、下载缓存、倍数基线缓存）。cookies 默认仍在 ~/.douyin-teardown。
os.environ.setdefault("TEARDOWN_DATA_DIR", str(DATA_DIR / "teardown"))

PARK_NEWSLETTER_FEED = "https://park-ai-intel.com/newsletter/feed.xml"
PARK_TEARDOWN_FEED = "https://park-ai-intel.com/teardown/feed.xml"

DOUYIN_HOSTS = ("douyin.com", "iesdouyin.com")


def ensure_dirs() -> None:
    for sub in ("reports", "newsletter", "topics", "jobs"):
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
