"""后台任务：同类任务串行（一次只拆一条、一次只跑一份日报），不同类互不阻塞（日报要跑很久，不能卡住拆解）。
状态落盘，重启后不会假装还在跑。"""
from __future__ import annotations

import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .models import Job, now_iso
from .store import JsonDir

MAX_LOG = 300


class JobContext:
    """交给任务函数的句柄：更新阶段、追加日志。"""

    def __init__(self, runner: "JobRunner", job_id: str):
        self._runner = runner
        self._id = job_id

    def stage(self, stage: str) -> None:
        self._runner._update(self._id, stage=stage)

    def log(self, line: str) -> None:
        self._runner._update(self._id, log_line=line)


class JobRunner:
    def __init__(self, store: JsonDir[Job]):
        self.store = store
        self._lock = threading.RLock()
        self._pools: dict[str, ThreadPoolExecutor] = {}
        self._interrupt_stale()

    def _interrupt_stale(self) -> None:
        for job in self.store.all():
            if job.state in ("queued", "running"):
                job.state, job.error, job.updated_at = "failed", "服务重启，任务被中断，请重新发起", now_iso()
                self.store.save(job)

    def _update(self, job_id: str, *, stage: str | None = None, log_line: str | None = None,
                state: str | None = None, error: str | None = None, result: dict | None = None) -> None:
        with self._lock:
            job = self.store.get(job_id)
            if job is None:
                return
            if stage is not None:
                job.stage = stage
            if log_line is not None:
                job.log = (job.log + [log_line])[-MAX_LOG:]
            if state is not None:
                job.state = state  # type: ignore[assignment]
            if error is not None:
                job.error = error
            if result is not None:
                job.result = result
            job.updated_at = now_iso()
            self.store.save(job)

    def active(self, kind: str) -> Job | None:
        return next((j for j in self.store.all() if j.kind == kind and j.state in ("queued", "running")), None)

    def submit(self, kind: str, input_: str, fn: Callable[[JobContext], dict]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, input=input_)  # type: ignore[arg-type]
        self.store.save(job)

        def run() -> None:
            self._update(job.id, state="running")
            ctx = JobContext(self, job.id)
            try:
                result = fn(ctx)
                self._update(job.id, state="done", result=result)
            except Exception as exc:  # noqa: BLE001 - 任务失败只记录，不让线程池吞掉
                ctx.log(traceback.format_exc(limit=3))
                self._update(job.id, state="failed", error=str(exc) or exc.__class__.__name__)

        with self._lock:
            pool = self._pools.setdefault(kind, ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"studio-{kind}"))
        pool.submit(run)
        return job
