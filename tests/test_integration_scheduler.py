from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.collector.adapter import (
    AntiCrawlError,
    CommunityAdapter,
    CommunityNotAccessibleError,
    FetchedPost,
)
from app.collector.rate_limit import RateLimiter
from app.collector.scheduler import CollectionScheduler
from app.collector.service import register_community, run_collection
from app.core.models import CollectionRun, Post


class _Adapter(CommunityAdapter):
    def parse_community_id(self, raw_url: str) -> str:
        return "app:1"

    def fetch_post_list(self, community_id: str, limit: int) -> list[dict]:
        return [{"taptap_post_id": "p1", "raw_url": "https://taptap.cn/x/1"}]

    def fetch_post_detail(self, post_ref: dict) -> FetchedPost:
        return FetchedPost(
            taptap_post_id=post_ref["taptap_post_id"],
            title="hello",
            content="world",
            author="u",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            reply_count=0,
            like_count=0,
            raw_url=post_ref["raw_url"],
        )

    def is_anti_crawl_response(self, status_code: int, body_sample: str) -> bool:
        return False


def test_scheduler_runs_collection_for_community(db_session, tmp_path):
    url = f"sqlite:///{(tmp_path / 'sched.db').as_posix()}"
    adapter = _Adapter()
    community = register_community(
        db_session,
        "https://taptap.cn/app/1",
        interval_seconds=60,
        per_run_limit=5,
        adapter=adapter,
    )

    collected_community_ids: list[int] = []

    def _collect(cid: int) -> None:
        collected_community_ids.append(cid)
        rl = RateLimiter(min_interval_seconds=0.0)
        run_collection(db_session, community, adapter, rl, max_retries=1)

    sched = CollectionScheduler(jobstore_url=url)
    sched.set_collect_function(_collect)
    sched.start()
    sched.trigger_now(community.id)
    sched.shutdown(wait=False)

    assert collected_community_ids == [community.id]
    posts = db_session.exec(__import__("sqlmodel").select(Post)).all()
    assert len(posts) == 1
    runs = db_session.exec(__import__("sqlmodel").select(CollectionRun)).all()
    assert len(runs) == 1
    assert runs[0].new_count == 1
