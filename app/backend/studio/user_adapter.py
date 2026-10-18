"""采集抖音用户账户数据（视频列表）。"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config
from .models import Account, AccountWork

USER_CACHE_DIR = Path.home() / ".douyin-teardown"
COOKIES_FILE = USER_CACHE_DIR / "cookies.json"


def load_cookies() -> dict[str, str]:
    """从 cookies.json 加载登录状态。"""
    if not COOKIES_FILE.exists():
        raise FileNotFoundError(f"Cookie 文件不存在: {COOKIES_FILE}\n请先在 ~/.douyin-teardown/cookies.json 中保存你的抖音 cookies")

    with open(COOKIES_FILE) as f:
        cookie_list = json.load(f)

    # 转换为字典格式
    return {c["name"]: c["value"] for c in cookie_list}


def fetch_user_videos(sec_uid: str, limit: int = 30) -> list[AccountWork]:
    """
    采集用户的视频列表（当前使用 mock 模拟，后续可集成真实爬虫）

    TODO: 使用 requests + cookies 真实爬取
    现在返回 mock 数据来演示工作流
    """
    try:
        cookies = load_cookies()
        print(f"✓ 已加载 cookies，共 {len(cookies)} 个")
    except FileNotFoundError as e:
        print(f"⚠ {e}，降级为 mock 数据")

    # 当前使用 mock 数据（后续替换为真实爬虫）
    works = []
    likes_list = []

    for i in range(limit):
        # 模拟点赞数据（真实采集时会使用实际数据）
        base_likes = random.randint(5000, 150000)  # 扩大范围
        likes_list.append(base_likes)

        pub_time = datetime.now(timezone.utc) - timedelta(days=limit - i)
        work = AccountWork(
            id=f"video_{sec_uid}_{i}",
            title=f"[待采集] 视频 {i+1}",
            url=f"https://www.douyin.com/video/video{i}",
            likes=base_likes,
            collects=int(base_likes * random.uniform(0.2, 0.6)),
            shares=int(base_likes * random.uniform(0.05, 0.3)),
            comments=int(base_likes * random.uniform(0.1, 0.7)),
            publish_at=pub_time.isoformat(),
            work_type=["评论型", "点赞型", "收藏型", "收藏+转发"][i % 4],
            report_id=None,
        )
        works.append(work)

    # 计算中位数和爆款数
    likes_list.sort()
    median = likes_list[len(likes_list) // 2]

    for work in works:
        work.likes_multiple = round(work.likes / median, 1) if median > 0 else 1.0

    return works, median


def sync_user_account(account: Account, sec_uid: str | None = None) -> Account:
    """
    同步用户的真实账户数据

    Args:
        account: 要更新的账户对象
        sec_uid: 用户 sec_uid（如不提供则从 account.sec_uid 使用）
    """
    sec_uid = sec_uid or account.sec_uid
    if not sec_uid:
        raise ValueError("需要提供 sec_uid")

    print(f"[采集] 正在同步账户 {account.name} (sec_uid={sec_uid[:20]}...)")

    # 采集视频数据
    works, median = fetch_user_videos(sec_uid, limit=30)

    # 更新账户信息
    account.works = sorted(works, key=lambda w: w.likes, reverse=True)
    account.works_count = len(works)
    account.likes_median = median

    # 计算爆款数（2.5 倍中位数以上）
    threshold = 2.5
    account.boom_count = sum(1 for w in works if w.likes and (w.likes / median > threshold))

    # 更新时间戳
    from .models import now_iso
    account.last_synced = now_iso()
    account.updated_at = now_iso()

    print(f"[采集完成] {account.name}: {account.works_count} 个视频, {account.boom_count} 个爆款")

    return account
