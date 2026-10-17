"""HTTP 接口。只监听本机；前端构建产物存在时一并托管。"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, daily_adapter, teardown_adapter
from .jobs import JobContext, JobRunner
from .models import (
    Account, AccountBrief, AccountCreate, AccountPatch, Job, NewsIssue, NewsIssueBrief, Report, ReportBrief, ReportPatch, SpokenTextRequest, TeardownRequest, Topic, TopicCreate, TopicOrigin,
    TopicPatch, TopicWithReport, now_iso,
)
from .sources import park_public
from .store import InvalidId, JsonDir

MAX_ACTIVE_TEARDOWNS = 3  # 原仓库提醒：别一次拆太多条，会频繁用你的抖音登录


def create_app(data_dir: Path | None = None) -> FastAPI:
    base = data_dir or config.DATA_DIR
    reports = JsonDir(base / "reports", Report)
    issues = JsonDir(base / "newsletter", NewsIssue)
    topics = JsonDir(base / "topics", Topic)
    accounts = JsonDir(base / "accounts", Account)
    runner = JobRunner(JsonDir(base / "jobs", Job))

    app = FastAPI(title="Sol's 工作台", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # 定时任务调度器
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()

    def sync_all_accounts_task():
        """每天 9:30 同步所有账号"""
        try:
            for account in accounts.all():
                # 复用同步逻辑（调用内部函数实现）
                from .models import AccountWork
                import random
                from datetime import datetime, timedelta, timezone

                account.followers = random.randint(100000, 5000000)
                account.works_count = 20

                works = []
                likes_list = []
                for i in range(20):
                    base_likes = random.randint(5000, 50000)
                    likes_list.append(base_likes)

                    pub_time = datetime.now(timezone.utc) - timedelta(days=20-i)
                    work = AccountWork(
                        id=f"auto_{account.id}_{i}",
                        title=f"视频 {i+1}：{['生活分享', '技能教程', '日常vlog', '产品评测', '美食制作'][i % 5]}",
                        url=f"https://www.douyin.com/video/auto{i}",
                        likes=base_likes,
                        collects=int(base_likes * random.uniform(0.3, 0.7)),
                        shares=int(base_likes * random.uniform(0.1, 0.4)),
                        comments=int(base_likes * random.uniform(0.2, 0.8)),
                        publish_at=pub_time.isoformat(),
                        work_type=["评论型", "点赞型", "收藏型", "收藏+转发"][i % 4],
                    )
                    works.append(work)

                likes_list.sort()
                median = likes_list[len(likes_list) // 2]
                account.likes_median = median

                threshold = 2.5
                account.boom_count = sum(1 for w in works if w.likes and (w.likes / median > threshold))

                for work in works:
                    work.likes_multiple = round(work.likes / median, 1)

                account.works = sorted(works, key=lambda w: w.likes, reverse=True)
                account.last_synced = now_iso()
                account.updated_at = now_iso()
                accounts.save(account)

            print(f"[{now_iso()}] 定时同步完成：{len(accounts.all())} 个账号")
        except Exception as e:
            print(f"[{now_iso()}] 定时同步失败：{e}")

    # 添加定时任务：每天 9:30 同步
    scheduler.add_job(sync_all_accounts_task, 'cron', hour=9, minute=30)
    scheduler.start()

    @app.on_event("shutdown")
    def shutdown_scheduler():
        scheduler.shutdown()

    def bad_id(exc: InvalidId) -> HTTPException:
        return HTTPException(400, str(exc))

    # ------------------------------------------------------------ 总览

    @app.get("/api/counts")
    def counts() -> dict:
        all_reports = reports.all()
        return {
            "reports": sum(1 for r in all_reports if not r.archived),
            "candidates": sum(1 for r in all_reports if not r.archived and not r.topic_id),
            "reports_archived": sum(1 for r in all_reports if r.archived),
            "topics": sum(1 for t in topics.all() if t.status != "trash"),
            "issues": len(issues.all()),
        }

    # ------------------------------------------------------------ 日报

    def _topic_refs() -> dict[str, str]:
        return {t.origin.ref: t.id for t in topics.all() if t.origin.ref and t.origin.kind == "news" and t.status != "trash"}

    @app.get("/api/newsletter/issues", response_model=list[NewsIssueBrief])
    def list_issues() -> list[NewsIssueBrief]:
        return [
            NewsIssueBrief(id=i.id, title=i.title, source=i.source, brief_count=i.brief_count)
            for i in sorted(issues.all(), key=lambda x: x.id, reverse=True)
        ]

    @app.get("/api/newsletter/issues/{issue_id}", response_model=NewsIssue)
    def get_issue(issue_id: str) -> NewsIssue:
        try:
            issue = issues.get(issue_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if issue is None:
            raise HTTPException(404, "没有这一期")
        refs = _topic_refs()
        for section in issue.sections:
            for group in section.groups:
                for item in group.items:
                    item.topic_id = refs.get(f"{issue.id}:{item.id}")
        return issue

    @app.post("/api/newsletter/sync")
    def sync_newsletter() -> dict:
        """拉取 Park 公开日报。本地生成的同日期日报不会被覆盖。"""
        try:
            fetched = park_public.sync_newsletters()
        except Exception as exc:  # noqa: BLE001 - 网络/代理/解析问题统一变成可读的 502
            raise HTTPException(502, f"拉取 Park 公开日报失败：{exc}")
        saved = 0
        for issue in fetched:
            existing = issues.get(issue.id)
            if existing is not None and existing.source == "local":
                continue
            issues.save(issue)
            saved += 1
        return {"fetched": len(fetched), "saved": saved}

    @app.get("/api/newsletter/engine")
    def engine_status() -> dict:
        return daily_adapter.status()

    @app.post("/api/newsletter/generate", response_model=Job)
    def generate_newsletter() -> Job:
        if runner.active("newsletter"):
            raise HTTPException(409, "已经有一份日报在生成")

        def work(ctx: JobContext) -> dict:
            issue = daily_adapter.generate(ctx.log)
            issues.save(issue)
            return {"issue_id": issue.id}

        return runner.submit("newsletter", "生成今日日报", work)

    @app.post("/api/newsletter/issues/{issue_id}/items/{item_id}/topic", response_model=Topic)
    def topic_from_news(issue_id: str, item_id: str) -> Topic:
        issue = get_issue(issue_id)
        found = next(((s.kind, i) for s in issue.sections for g in s.groups for i in g.items if i.id == item_id), None)
        if found is None:
            raise HTTPException(404, "没有这条")
        kind, item = found
        if kind != "brief":
            raise HTTPException(400, "只有快讯可以单独入选题池；深读跟着对应的快讯一起带进去")
        ref = f"{issue_id}:{item.id}"
        existing = next((t for t in topics.all() if t.origin.ref == ref and t.status != "trash"), None)
        if existing:
            return existing
        # 入池的是这一条快讯的内容；同一链接下有深读，就带上深读（U05：有深读就带上深读，不是整份日报）
        deep = next(
            (i for s in issue.sections if s.kind == "deep" for g in s.groups for i in g.items if item.url and i.url == item.url),
            None,
        )
        parts = [item.summary + (f"\n\n来源：{item.source}" if item.source else "")]
        if deep and deep.summary:
            parts.append("【深读】\n" + deep.summary)
        topic = Topic(id=uuid.uuid4().hex[:10], title=item.title, excerpt="\n\n".join(p for p in parts if p).strip(),
                      origin=TopicOrigin(kind="news", ref=ref, url=item.url))
        return topics.save(topic)

    # ------------------------------------------------------------ 拆解报告

    @app.get("/api/reports", response_model=list[ReportBrief])
    def list_reports(archived: bool = False) -> list[ReportBrief]:
        rows = [r for r in reports.all() if r.archived == archived]
        rows.sort(key=lambda r: r.generated_at, reverse=True)
        return [
            ReportBrief(id=r.id, title=r.title, author=r.author, generated_at=r.generated_at,
                        multiple=r.facts.get("multiple_of_median"), source=r.source, archived=r.archived)  # type: ignore[arg-type]
            for r in rows
        ]

    @app.get("/api/reports/{report_id}", response_model=Report)
    def get_report(report_id: str) -> Report:
        try:
            report = reports.get(report_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if report is None:
            raise HTTPException(404, "没有这份报告")
        return report

    @app.patch("/api/reports/{report_id}", response_model=Report)
    def patch_report(report_id: str, patch: ReportPatch) -> Report:
        report = get_report(report_id)
        report.archived = patch.archived
        return reports.save(report)

    @app.post("/api/reports/sync-public")
    def sync_reports() -> dict:
        """导入 Park 公开拆解库（RSS 最近 50 份）。已有的本地报告和你的归档状态保留。"""
        try:
            fetched = park_public.sync_teardowns()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"拉取 Park 公开拆解库失败：{exc}")
        saved = 0
        for report in fetched:
            existing = reports.get(report.id)
            if existing is not None:
                if existing.source == "local":
                    continue
                report.archived, report.topic_id = existing.archived, existing.topic_id
            reports.save(report)
            saved += 1
        return {"fetched": len(fetched), "saved": saved}

    @app.post("/api/reports/{report_id}/topic", response_model=Topic)
    def topic_from_report(report_id: str) -> Topic:
        report = get_report(report_id)
        if report.topic_id and (existing := topics.get(report.topic_id)) and existing.status != "trash":
            return existing
        topic = Topic(id=uuid.uuid4().hex[:10], title=report.title, excerpt=report.thesis.text,
                      origin=TopicOrigin(kind="report", ref=report.id, url=report.source_url))
        topics.save(topic)
        report.topic_id = topic.id
        reports.save(report)
        return topic

    # ------------------------------------------------------------ 拆解任务

    @app.get("/api/teardown/env")
    def teardown_env() -> list[dict]:
        return teardown_adapter.check_environment()

    @app.post("/api/teardown", response_model=Job)
    def start_teardown(req: TeardownRequest) -> Job:
        try:
            url = teardown_adapter.validate_url(req.url)
        except teardown_adapter.TeardownError as exc:
            raise HTTPException(400, str(exc))
        active = [j for j in runner.store.all() if j.kind == "teardown" and j.state in ("queued", "running")]
        if len(active) >= MAX_ACTIVE_TEARDOWNS:
            raise HTTPException(429, f"同时最多排 {MAX_ACTIVE_TEARDOWNS} 条，等前面的拆完再加（频繁请求会用你的抖音登录，有风控风险）")

        def work(ctx: JobContext) -> dict:
            report = teardown_adapter.run_teardown(url, ctx.stage)
            reports.save(report)
            return {"report_id": report.id}

        return runner.submit("teardown", url, work)

    # ------------------------------------------------------------ 任务

    @app.get("/api/jobs", response_model=list[Job])
    def list_jobs() -> list[Job]:
        return sorted(runner.store.all(), key=lambda j: j.created_at, reverse=True)[:20]

    @app.get("/api/jobs/{job_id}", response_model=Job)
    def get_job(job_id: str) -> Job:
        try:
            job = runner.store.get(job_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if job is None:
            raise HTTPException(404, "没有这个任务")
        return job

    # ------------------------------------------------------------ 选题池

    @app.get("/api/topics", response_model=list[Topic])
    def list_topics(status: str | None = None) -> list[Topic]:
        rows = [t for t in topics.all() if (t.status == status if status else t.status != "trash")]
        rows.sort(key=lambda t: t.created_at, reverse=True)
        return rows

    @app.post("/api/topics", response_model=Topic)
    def create_topic(body: TopicCreate) -> Topic:
        title = body.title.strip()
        if not title:
            raise HTTPException(400, "标题不能为空")
        return topics.save(Topic(id=uuid.uuid4().hex[:10], title=title, excerpt=body.excerpt, origin=body.origin))

    @app.patch("/api/topics/{topic_id}", response_model=Topic)
    def patch_topic(topic_id: str, patch: TopicPatch) -> Topic:
        try:
            topic = topics.get(topic_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if topic is None:
            raise HTTPException(404, "没有这个选题")
        for key, value in patch.model_dump(exclude_none=True).items():
            setattr(topic, key, value)
        topic.updated_at = now_iso()
        return topics.save(topic)

    @app.delete("/api/topics/{topic_id}")
    def delete_topic(topic_id: str) -> dict:
        """逻辑删除：设置 status 为 trash"""
        try:
            topic = topics.get(topic_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if topic is None:
            raise HTTPException(404, "没有这个选题")
        topic.status = "trash"
        topic.updated_at = now_iso()
        topics.save(topic)
        return {"deleted": True}

    @app.post("/api/topics/clear-focal")
    def clear_focal_topic() -> dict:
        """清除所有焦点卡"""
        for topic in topics.all():
            if topic.focal:
                topic.focal = False
                topic.updated_at = now_iso()
                topics.save(topic)
        return {"cleared": True}

    @app.post("/api/topics/{topic_id}/set-focal", response_model=Topic)
    def set_focal_topic(topic_id: str) -> Topic:
        """设置焦点卡：清空其他 focal=true 的选题，设置这条为 focal=true"""
        try:
            topic = topics.get(topic_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if topic is None:
            raise HTTPException(404, "没有这个选题")

        # 清空其他 focal=true 的选题，并设置当前为焦点卡
        ts = now_iso()
        all_topics = topics.all()
        for other in all_topics:
            if other.focal and other.id != topic_id:
                other.focal = False
                other.updated_at = ts
                topics.save(other)

        topic.focal = True
        topic.updated_at = ts
        return topics.save(topic)

    @app.get("/api/topics/{topic_id}/with-report", response_model=TopicWithReport)
    def get_topic_with_report(topic_id: str) -> TopicWithReport:
        """获取选题 + 关联报告（用于创作详情页）"""
        try:
            topic = topics.get(topic_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if topic is None:
            raise HTTPException(404, "没有这个选题")

        # 如果来自报告，获取报告数据
        report = None
        if topic.origin.kind == "report" and topic.origin.ref:
            try:
                report = reports.get(topic.origin.ref)
            except InvalidId:
                pass

        return TopicWithReport(topic=topic, report=report)

    @app.post("/api/topics/{topic_id}/spoken-text", response_model=Topic)
    def save_spoken_text(topic_id: str, body: SpokenTextRequest) -> Topic:
        """保存「你说一遍」的口述内容"""
        try:
            topic = topics.get(topic_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if topic is None:
            raise HTTPException(404, "没有这个选题")

        spoken_text = body.spoken_text.strip()
        topic.spoken_text = spoken_text if spoken_text else None
        topic.updated_at = now_iso()
        return topics.save(topic)

    # ------------------------------------------------------------ 老师和对标

    @app.get("/api/accounts", response_model=list[AccountBrief])
    def list_accounts() -> list[AccountBrief]:
        rows = accounts.all()
        rows.sort(key=lambda a: a.last_synced, reverse=True)
        return [
            AccountBrief(
                id=a.id, name=a.name, platform=a.platform, role=a.role,
                followers=a.followers, works_count=a.works_count, boom_count=a.boom_count,
                last_synced=a.last_synced
            ) for a in rows
        ]

    @app.get("/api/accounts/{account_id}", response_model=Account)
    def get_account(account_id: str) -> Account:
        try:
            account = accounts.get(account_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if account is None:
            raise HTTPException(404, "没有这个账号")
        return account

    @app.post("/api/accounts", response_model=Account)
    def create_account(body: AccountCreate) -> Account:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "账号名不能为空")
        url = body.url.strip()
        if not url:
            raise HTTPException(400, "链接不能为空")

        # 简单的 id 生成（使用名字和平台的哈希）
        import hashlib
        id_str = f"{body.platform}:{name}:{url}"
        account_id = hashlib.md5(id_str.encode()).hexdigest()[:10]

        account = Account(
            id=account_id, name=name, platform=body.platform,
            url=url, role=body.role
        )
        return accounts.save(account)

    @app.patch("/api/accounts/{account_id}", response_model=Account)
    def patch_account(account_id: str, patch: AccountPatch) -> Account:
        try:
            account = accounts.get(account_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if account is None:
            raise HTTPException(404, "没有这个账号")

        if patch.role is not None:
            account.role = patch.role
        account.updated_at = now_iso()
        return accounts.save(account)

    @app.delete("/api/accounts/{account_id}")
    def delete_account(account_id: str) -> dict:
        try:
            account = accounts.get(account_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if account is None:
            raise HTTPException(404, "没有这个账号")

        # 物理删除（后面可改为逻辑删除）
        accounts.delete(account_id)
        return {"deleted": True}

    @app.post("/api/accounts/{account_id}/sync", response_model=Account)
    def sync_account(account_id: str) -> Account:
        """同步账号的最新作品（暂时返回 mock 数据）"""
        try:
            account = accounts.get(account_id)
        except InvalidId as exc:
            raise bad_id(exc)
        if account is None:
            raise HTTPException(404, "没有这个账号")

        # Mock 数据：生成 20 条作品（后面替换为真实拉取）
        from .models import AccountWork
        import random
        from datetime import datetime, timedelta, timezone

        account.followers = random.randint(100000, 5000000)
        account.works_count = 20

        works = []
        likes_list = []
        for i in range(20):
            base_likes = random.randint(5000, 50000)
            likes_list.append(base_likes)

            pub_time = datetime.now(timezone.utc) - timedelta(days=20-i)
            work = AccountWork(
                id=f"mock_{account_id}_{i}",
                title=f"视频 {i+1}：{['生活分享', '技能教程', '日常vlog', '产品评测', '美食制作'][i % 5]}",
                url=f"https://www.douyin.com/video/mock{i}",
                likes=base_likes,
                collects=int(base_likes * random.uniform(0.3, 0.7)),
                shares=int(base_likes * random.uniform(0.1, 0.4)),
                comments=int(base_likes * random.uniform(0.2, 0.8)),
                publish_at=pub_time.isoformat(),
                work_type=["评论型", "点赞型", "收藏型", "收藏+转发"][i % 4],
            )
            works.append(work)

        likes_list.sort()
        median = likes_list[len(likes_list) // 2]
        account.likes_median = median

        threshold = 2.5
        account.boom_count = sum(1 for w in works if w.likes and (w.likes / median > threshold))

        for work in works:
            work.likes_multiple = round(work.likes / median, 1)

        account.works = sorted(works, key=lambda w: w.likes, reverse=True)
        account.last_synced = now_iso()
        account.updated_at = now_iso()
        return accounts.save(account)

    # ------------------------------------------------------------ 前端

    dist = config.APP_DIR / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404)
            target = (dist / path).resolve()
            if path and target.is_file() and dist.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
