from __future__ import annotations

import logging
from datetime import timezone, timedelta
from typing import Callable, Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def _job_id(community_id: int) -> str:
    return f"collect-community-{community_id}"


class CollectionScheduler:
    """基于 APScheduler 的采集调度器。

    - 使用 SQLAlchemyJobStore 指向同一 SQLite，进程重启后自动恢复 job。
    - 按 community.interval_seconds 创建 interval job。
    """

    def __init__(self, jobstore_url: str):
        self._scheduler = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=jobstore_url)},
            timezone=timezone(timedelta(hours=8)),
        )
        self._collect_fn: Optional[Callable[[int], None]] = None

    def set_collect_function(self, fn: Callable[[int], None]) -> None:
        self._collect_fn = fn

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("CollectionScheduler started")

    def shutdown(self, wait: bool = False) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)

    def schedule_community(self, community_id: int, interval_seconds: int, replace: bool = True) -> None:
        if self._collect_fn is None:
            raise RuntimeError("未设置 collect function，请先 set_collect_function")

        self._scheduler.add_job(
            func=self._collect_fn,
            trigger=IntervalTrigger(seconds=interval_seconds),
            args=[community_id],
            id=_job_id(community_id),
            replace_existing=replace,
        )
        logger.info("scheduled community %s every %ss", community_id, interval_seconds)

    def unschedule_community(self, community_id: int) -> None:
        try:
            self._scheduler.remove_job(_job_id(community_id))
        except Exception:
            pass

    def trigger_now(self, community_id: int) -> None:
        """手动触发一次，不影响原有定时计划。"""
        if self._collect_fn is None:
            raise RuntimeError("未设置 collect function")
        self._collect_fn(community_id)

    def get_jobs(self) -> list[dict]:
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run_time": job.next_run_time,
                "trigger": str(job.trigger),
            })
        return jobs

    @property
    def running(self) -> bool:
        return self._scheduler.running
