"""接口测试：临时数据目录 + 真实 fixtures，不碰网络、不碰你的 data/。"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio import teardown_adapter
from studio.main import create_app
from studio.parsers.report import parse_report_markdown
from studio.sources import park_public

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    def fake_fetch(url, **_):
        name = "newsletter-feed.xml" if "newsletter" in url else "teardown-feed.xml"
        return park_public.parse_feed((FIX / name).read_bytes())

    monkeypatch.setattr(park_public, "fetch_feed", fake_fetch)
    return TestClient(create_app(tmp_path))


def wait_job(client, job_id, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("任务超时")


# ------------------------------------------------------------- 日报


def test_newsletter_sync_and_read(client):
    assert client.get("/api/newsletter/issues").json() == []
    r = client.post("/api/newsletter/sync").json()
    assert r["fetched"] == r["saved"] >= 20
    issues = client.get("/api/newsletter/issues").json()
    assert issues == sorted(issues, key=lambda i: i["id"], reverse=True)
    issue = client.get(f"/api/newsletter/issues/{issues[0]['id']}").json()
    assert issue["sections"][0]["kind"] == "brief"


def test_news_item_to_topic_is_single_item_and_idempotent(client):
    client.post("/api/newsletter/sync")
    issue_id = client.get("/api/newsletter/issues").json()[0]["id"]
    issue = client.get(f"/api/newsletter/issues/{issue_id}").json()
    item = issue["sections"][0]["groups"][0]["items"][0]

    t1 = client.post(f"/api/newsletter/issues/{issue_id}/items/{item['id']}/topic").json()
    assert t1["title"] == item["title"]
    assert item["summary"] in t1["excerpt"], "入池的应是这一条的内容"
    assert len(t1["excerpt"]) < 3000, "不能把整份日报塞进去"
    t2 = client.post(f"/api/newsletter/issues/{issue_id}/items/{item['id']}/topic").json()
    assert t1["id"] == t2["id"], "重复点不应重复入池"

    again = client.get(f"/api/newsletter/issues/{issue_id}").json()
    marked = [i for g in again["sections"][0]["groups"] for i in g["items"] if i["topic_id"]]
    assert [m["id"] for m in marked] == [item["id"]]

    # 不做了之后可以重新入池
    client.patch(f"/api/topics/{t1['id']}", json={"status": "trash"})
    t3 = client.post(f"/api/newsletter/issues/{issue_id}/items/{item['id']}/topic").json()
    assert t3["id"] != t1["id"]


def test_issue_not_found_and_bad_id(client):
    assert client.get("/api/newsletter/issues/2000-01-01").status_code == 404
    assert client.get("/api/newsletter/issues/..%2Fsecret").status_code in (400, 404)


def test_local_issue_not_overwritten_by_public_sync(client, tmp_path):
    client.post("/api/newsletter/sync")
    issue_id = client.get("/api/newsletter/issues").json()[0]["id"]
    local = client.get(f"/api/newsletter/issues/{issue_id}").json()
    local["source"], local["title"] = "local", "我自己生成的"
    (tmp_path / "newsletter" / f"{issue_id}.json").write_text(__import__("json").dumps(local, ensure_ascii=False), encoding="utf-8")
    client.post("/api/newsletter/sync")
    assert client.get(f"/api/newsletter/issues/{issue_id}").json()["title"] == "我自己生成的"


# ------------------------------------------------------------- 拆解报告


def test_reports_sync_list_archive(client):
    r = client.post("/api/reports/sync-public").json()
    assert r["saved"] == 50
    live = client.get("/api/reports").json()
    assert len(live) == 50 and live[0]["generated_at"] >= live[-1]["generated_at"]

    rid = live[0]["id"]
    assert client.patch(f"/api/reports/{rid}", json={"archived": True}).json()["archived"] is True
    assert len(client.get("/api/reports").json()) == 49
    assert [x["id"] for x in client.get("/api/reports?archived=true").json()] == [rid]

    # 再次同步不应把归档状态冲掉
    client.post("/api/reports/sync-public")
    assert client.get(f"/api/reports/{rid}").json()["archived"] is True


def test_report_to_topic(client):
    client.post("/api/reports/sync-public")
    rid = client.get("/api/reports").json()[0]["id"]
    topic = client.post(f"/api/reports/{rid}/topic").json()
    assert topic["origin"]["kind"] == "report" and topic["origin"]["ref"] == rid
    assert client.get(f"/api/reports/{rid}").json()["topic_id"] == topic["id"]
    assert client.post(f"/api/reports/{rid}/topic").json()["id"] == topic["id"]


# ------------------------------------------------------------- 拆解任务


def test_teardown_rejects_non_douyin_url(client):
    for bad in ("https://example.com/video/1", "not a url", "https://evildouyin.com/x", "javascript:alert(1)"):
        r = client.post("/api/teardown", json={"url": bad})
        assert r.status_code == 400, bad


def test_teardown_job_stages_and_result(client, monkeypatch):
    example = parse_report_markdown((FIX / "example-report.md").read_text(encoding="utf-8"), source="local")
    seen = []

    def fake_run(url, on_stage, **_):
        for stage in ("downloading", "transcribing", "analyzing"):
            on_stage(stage)
            seen.append(stage)
            time.sleep(0.05)
        return example

    monkeypatch.setattr(teardown_adapter, "run_teardown", fake_run)
    job = client.post("/api/teardown", json={"url": "https://v.douyin.com/abc/"}).json()
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    assert done["result"] == {"report_id": example.id}
    assert seen == ["downloading", "transcribing", "analyzing"]
    saved = client.get(f"/api/reports/{example.id}").json()
    assert saved["source"] == "local" and saved["facts"]["multiple_of_median"] == 323.9


def test_teardown_failure_is_reported_not_swallowed(client, monkeypatch):
    def boom(url, on_stage, **_):
        on_stage("downloading")
        raise teardown_adapter.TeardownError("cookies 缺失")

    monkeypatch.setattr(teardown_adapter, "run_teardown", boom)
    job = client.post("/api/teardown", json={"url": "https://v.douyin.com/abc/"}).json()
    done = wait_job(client, job["id"])
    assert done["state"] == "failed" and "cookies 缺失" in done["error"]
    assert done["stage"] == "downloading"


def test_teardown_queue_limit(client, monkeypatch):
    gate = {"open": False}

    def slow(url, on_stage, **_):
        while not gate["open"]:
            time.sleep(0.02)
        raise teardown_adapter.TeardownError("x")

    monkeypatch.setattr(teardown_adapter, "run_teardown", slow)
    codes = [client.post("/api/teardown", json={"url": f"https://v.douyin.com/{i}/"}).status_code for i in range(5)]
    gate["open"] = True
    assert codes == [200, 200, 200, 429, 429], "同时最多 3 条，防止批量触发风控"


def test_stale_jobs_marked_failed_on_restart(tmp_path):
    from studio.jobs import JobRunner
    from studio.models import Job
    from studio.store import JsonDir

    store = JsonDir(tmp_path / "jobs", Job)
    store.save(Job(id="old1", kind="teardown", state="running"))
    JobRunner(store)
    assert store.get("old1").state == "failed"


# ------------------------------------------------------------- 选题池


def test_topic_crud_and_validation(client):
    assert client.post("/api/topics", json={"title": "  ", "origin": {"kind": "manual"}}).status_code == 400
    t = client.post("/api/topics", json={"title": "我的选题", "origin": {"kind": "manual"}}).json()
    assert t["stage"] == "选题" and t["status"] == "pool"
    assert client.patch(f"/api/topics/{t['id']}", json={"stage": "提纲"}).json()["stage"] == "提纲"
    assert client.patch(f"/api/topics/{t['id']}", json={"stage": "乱写"}).status_code == 422
    assert [x["id"] for x in client.get("/api/topics").json()] == [t["id"]]
    client.patch(f"/api/topics/{t['id']}", json={"status": "trash"})
    assert client.get("/api/topics").json() == []
    assert len(client.get("/api/topics?status=trash").json()) == 1
    assert client.get("/api/counts").json()["topics"] == 0
    assert client.delete(f"/api/topics/{t['id']}").json() == {"deleted": True}
    assert client.patch("/api/topics/nope", json={"stage": "提纲"}).status_code == 404


def test_http_client_works_under_socks_proxy_env(monkeypatch):
    """回归：用户机器设了 ALL_PROXY=socks5h://…，httpx 需要 socksio，否则同步直接 500。"""
    import httpx

    monkeypatch.setenv("ALL_PROXY", "socks5h://127.0.0.1:1")
    httpx.Client(headers=park_public.HEADERS, timeout=1, follow_redirects=True).close()


def test_long_newsletter_job_does_not_block_teardown(client, monkeypatch):
    """日报生成要十几分钟到半小时，期间拆解必须照常跑。"""
    from studio import daily_adapter

    gate = {"open": False}

    def slow_generate(log, **_):
        while not gate["open"]:
            time.sleep(0.02)
        raise RuntimeError("stop")

    example = parse_report_markdown((FIX / "example-report.md").read_text(encoding="utf-8"), source="local")
    monkeypatch.setattr(daily_adapter, "generate", slow_generate)
    monkeypatch.setattr(teardown_adapter, "run_teardown", lambda url, on_stage, **_: example)

    nl = client.post("/api/newsletter/generate").json()
    td = client.post("/api/teardown", json={"url": "https://v.douyin.com/abc/"}).json()
    assert wait_job(client, td["id"])["state"] == "done"
    assert client.get(f"/api/jobs/{nl['id']}").json()["state"] == "running"
    gate["open"] = True
    assert wait_job(client, nl["id"])["state"] == "failed"


def test_deep_read_is_attached_to_matching_brief_and_deep_cannot_be_pooled(client):
    """U05：每条快讯单独入选题池，有深读就带上深读；深读自己没有入池入口。"""
    client.post("/api/newsletter/sync")
    issue_id = client.get("/api/newsletter/issues").json()[0]["id"]
    issue = client.get(f"/api/newsletter/issues/{issue_id}").json()
    brief = next(s for s in issue["sections"] if s["kind"] == "brief")
    deep = next(s for s in issue["sections"] if s["kind"] == "deep")
    deep_items = {i["url"]: i for g in deep["groups"] for i in g["items"] if i["url"]}
    with_deep = next(i for g in brief["groups"] for i in g["items"] if i["url"] in deep_items)
    without = next(i for g in brief["groups"] for i in g["items"] if i["url"] not in deep_items)

    t = client.post(f"/api/newsletter/issues/{issue_id}/items/{with_deep['id']}/topic").json()
    assert "【深读】" in t["excerpt"] and deep_items[with_deep["url"]]["summary"][:30] in t["excerpt"]
    t2 = client.post(f"/api/newsletter/issues/{issue_id}/items/{without['id']}/topic").json()
    assert "【深读】" not in t2["excerpt"]

    any_deep = next(iter(deep_items.values()))
    assert client.post(f"/api/newsletter/issues/{issue_id}/items/{any_deep['id']}/topic").status_code == 400


def test_candidates_count_excludes_archived_and_pooled(client):
    client.post("/api/reports/sync-public")
    base = client.get("/api/counts").json()
    assert base["candidates"] == base["reports"] == 50
    rid = client.get("/api/reports").json()[0]["id"]
    client.post(f"/api/reports/{rid}/topic")
    assert client.get("/api/counts").json()["candidates"] == 49
    rid2 = client.get("/api/reports").json()[1]["id"]
    client.patch(f"/api/reports/{rid2}", json={"archived": True})
    c = client.get("/api/counts").json()
    assert c["candidates"] == 48 and c["reports"] == 49
