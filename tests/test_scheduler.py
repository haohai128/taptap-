from __future__ import annotations

import time

from apscheduler.schedulers.background import BackgroundScheduler

from app.collector.scheduler import CollectionScheduler


# 模块级函数，供 APSerializer 序列化 jobstore
_collected: list[int] = []


def _collect(cid: int) -> None:
    _collected.append(cid)


def test_scheduler_persists_and_recovers(tmp_path):
    url = f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}"

    sched1 = CollectionScheduler(jobstore_url=url)
    sched1.set_collect_function(_collect)
    sched1.start()
    sched1.schedule_community(community_id=1, interval_seconds=60)
    sched1.shutdown(wait=False)

    sched2 = CollectionScheduler(jobstore_url=url)
    sched2.set_collect_function(_collect)
    sched2.start()
    jobs = sched2.get_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "collect-community-1"
    sched2.shutdown(wait=False)


def test_scheduler_trigger_now_does_not_duplicate(tmp_path):
    global _collected
    _collected = []
    url = f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}"
    sched = CollectionScheduler(jobstore_url=url)
    sched.set_collect_function(_collect)
    sched.start()
    sched.schedule_community(community_id=7, interval_seconds=600)
    sched.trigger_now(7)
    assert _collected == [7]
    assert len(sched.get_jobs()) == 1
    sched.shutdown(wait=False)


def test_scheduler_interval_matches_config(tmp_path):
    url = f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}"
    sched = CollectionScheduler(jobstore_url=url)
    sched.set_collect_function(_collect)
    sched.start()
    sched.schedule_community(community_id=3, interval_seconds=120)
    jobs = sched.get_jobs()
    assert "0:02:00" in jobs[0]["trigger"]
    sched.shutdown(wait=False)

