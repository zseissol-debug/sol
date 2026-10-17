"""数据契约。前端 frontend/src/types.ts 与这里一一对应。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Source = Literal["park_public", "local"]
STAGES = ("选题", "提纲", "录制", "剪辑", "待发", "已发出")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- 拆解报告


class Evidence(BaseModel):
    start: float
    end: float = 0
    quote: str = ""


class Conclusion(BaseModel):
    text: str
    evidence: list[Evidence] = Field(default_factory=list)


class Segment(BaseModel):
    index: int
    label: str  # 钩子 承诺 论点 案例 跑题 收束 引导
    drift: bool = False
    start: float
    end: float
    summary: str = ""
    reason: str = ""
    text: str = ""


class Opening(BaseModel):
    """只有拆自己的视频时才有：观众平均看到的前 N 秒。"""

    seconds: float
    analysis: str
    transcript: str = ""


class Report(BaseModel):
    id: str  # 抖音视频 id
    title: str
    author: Optional[str] = None
    source_url: Optional[str] = None
    generated_at: str
    duration_seconds: float = 0
    facts: dict[str, float | int | None] = Field(default_factory=dict)
    thesis: Conclusion
    opening: Optional[Opening] = None
    segments: list[Segment] = Field(default_factory=list)
    drift_seconds: float = 0
    drift_share: float = 0
    why_boom: list[Conclusion] = Field(default_factory=list)
    why_scatter: list[Conclusion] = Field(default_factory=list)
    hypothesis_note: str = ""
    source: Source = "local"
    archived: bool = False
    topic_id: Optional[str] = None  # 已入选题池时指向选题


class ReportBrief(BaseModel):
    """列表用的精简字段。"""

    id: str
    title: str
    author: Optional[str]
    generated_at: str
    multiple: Optional[float]
    source: Source
    archived: bool


# ---------------------------------------------------------------- AI 日报


class NewsItem(BaseModel):
    id: str
    title: str
    url: Optional[str] = None
    source: Optional[str] = None  # 如 "Claude Devs X / ClaudeDevs"
    summary: str = ""
    topic_id: Optional[str] = None


class NewsGroup(BaseModel):
    name: Optional[str] = None  # 如 "底层工具"
    items: list[NewsItem] = Field(default_factory=list)


class NewsSection(BaseModel):
    kind: Literal["brief", "deep", "radar", "other"]
    title: str
    groups: list[NewsGroup] = Field(default_factory=list)
    text: Optional[str] = None


class NewsIssue(BaseModel):
    id: str  # 日期 YYYY-MM-DD
    title: str
    published_at: Optional[str] = None
    source: Source = "park_public"
    sections: list[NewsSection] = Field(default_factory=list)
    brief_count: int = 0


class NewsIssueBrief(BaseModel):
    id: str
    title: str
    source: Source
    brief_count: int


# ---------------------------------------------------------------- 选题


class TopicOrigin(BaseModel):
    kind: Literal["news", "report", "manual"]
    ref: Optional[str] = None  # 日报条目 id / 报告 id
    url: Optional[str] = None


class Topic(BaseModel):
    id: str
    title: str
    origin: TopicOrigin
    excerpt: str = ""  # 入池时带上的那一条的内容（日报：单条原文，不是整份日报）
    stage: Literal["选题", "提纲", "录制", "剪辑", "待发", "已发出"] = "选题"
    status: Literal["pool", "scheduled", "trash"] = "pool"
    focal: bool = False  # 是否是焦点卡的那一条
    qa_conclusion: Optional[Literal["go", "patch", "thin"]] = "go"  # QA 评分结论，默认 go
    spoken_text: Optional[str] = None  # 「你说一遍」的口述内容
    video_project_path: Optional[str] = None  # 关联的剪辑项目完整路径
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class TopicCreate(BaseModel):
    title: str
    origin: TopicOrigin
    excerpt: str = ""


class TopicPatch(BaseModel):
    title: Optional[str] = None
    status: Optional[Literal["pool", "scheduled", "trash"]] = None
    stage: Optional[Literal["选题", "提纲", "录制", "剪辑", "待发", "已发出"]] = None
    qa_conclusion: Optional[Literal["go", "patch", "thin"]] = None
    spoken_text: Optional[str] = None
    video_project_path: Optional[str] = None
    # 注意：focal 字段只能通过 POST /api/topics/{id}/set-focal 修改


# ---------------------------------------------------------------- 请求体


class ReportPatch(BaseModel):
    archived: bool


class SpokenTextRequest(BaseModel):
    spoken_text: str


class TopicWithReport(BaseModel):
    topic: Topic
    report: Optional[Report] = None


class TeardownRequest(BaseModel):
    url: str


# ---------------------------------------------------------------- 老师和对标


class AccountWork(BaseModel):
    """账号的单条作品。"""
    id: str  # 视频 id
    title: str
    url: str
    likes: int
    collects: int = 0
    shares: int = 0
    comments: int = 0
    publish_at: str
    likes_multiple: Optional[float] = None  # 点赞倍数（vs 账号中位数）
    work_type: Optional[str] = None  # 互动类型：评论型、点赞型、收藏型、收藏+转发


class Account(BaseModel):
    id: str
    name: str
    platform: Literal["douyin", "xiaohongshu", "x", "bilibili"]
    sec_uid: Optional[str] = None  # 抖音 id
    url: str
    role: Literal["teacher", "peer"]  # 老师 / 对标
    followers: Optional[int] = None
    likes_median: Optional[int] = None  # 最近 60 条的中位数
    works_count: int = 0  # 最近拉取的作品数（最多 60）
    boom_count: int = 0  # 爆款数（倍数 > 2.5x）
    works: list[AccountWork] = Field(default_factory=list)
    last_synced: str = Field(default_factory=now_iso)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class AccountBrief(BaseModel):
    """列表用的精简字段。"""
    id: str
    name: str
    platform: Literal["douyin", "xiaohongshu", "x", "bilibili"]
    role: Literal["teacher", "peer"]
    followers: Optional[int]
    works_count: int
    boom_count: int
    last_synced: str


class AccountCreate(BaseModel):
    """添加账号的请求体。"""
    name: str
    platform: Literal["douyin", "xiaohongshu", "x", "bilibili"]
    url: str
    role: Literal["teacher", "peer"] = "peer"  # 默认对标


class AccountPatch(BaseModel):
    """更新账号的请求体。"""
    role: Optional[Literal["teacher", "peer"]] = None


# ---------------------------------------------------------------- 任务


class Job(BaseModel):
    id: str
    kind: Literal["teardown", "newsletter"]
    input: str = ""
    state: Literal["queued", "running", "done", "failed"] = "queued"
    stage: str = ""  # teardown: downloading / transcribing / analyzing
    error: Optional[str] = None
    result: dict = Field(default_factory=dict)
    log: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
