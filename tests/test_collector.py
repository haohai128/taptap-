from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
import pytest

from app.collector.adapter import (
    AntiCrawlError,
    CommunityAdapter,
    CommunityNotAccessibleError,
    FetchedPost,
)
from app.collector.rate_limit import RateLimiter
from app.collector.retry import MaxRetriesExceeded, retry_with_backoff
from app.collector.taptap_adapter import TapTapAdapter
from app.collector.service import (
    DuplicateCommunityError,
    register_community,
    run_collection,
    upsert_post,
)
from app.core.models import Community, Post, PostStatus
from app.core.tz import now_cn


class FakeAdapter(CommunityAdapter):
    def __init__(self, posts: list[FetchedPost], anti_crawl_at: Optional[int] = None):
        self._posts = posts
        self._anti_crawl_at = anti_crawl_at
        self._calls = 0

    def parse_community_id(self, raw_url: str) -> str:
        if "invalid" in raw_url:
            raise ValueError("invalid")
        return "app:1"

    def fetch_post_list(self, community_id: str, limit: int) -> list[dict]:
        self._calls += 1
        if self._anti_crawl_at == 0:
            raise AntiCrawlError("blocked")
        return [
            {"taptap_post_id": p.taptap_post_id, "raw_url": p.raw_url}
            for p in self._posts[:limit]
        ]

    def fetch_post_detail(self, post_ref: dict) -> FetchedPost:
        self._calls += 1
        if self._anti_crawl_at is not None and self._calls >= self._anti_crawl_at:
            raise AntiCrawlError("blocked in detail")
        for p in self._posts:
            if p.taptap_post_id == post_ref["taptap_post_id"]:
                return p
        raise KeyError(post_ref)

    def is_anti_crawl_response(self, status_code: int, body_sample: str) -> bool:
        return status_code in (403, 429)


def _make_post(pid: str = "p1") -> FetchedPost:
    return FetchedPost(
        taptap_post_id=pid,
        title="t",
        content="c",
        author="a",
        published_at=datetime(2024, 1, 1),
        reply_count=1,
        like_count=2,
        raw_url="https://example.com/p/1",
    )


def test_parse_community_id_app_url():
    adapter = TapTapAdapter(httpx.Client())
    assert adapter.parse_community_id("https://www.taptap.cn/app/12345") == "app:12345"


def test_parse_community_id_invalid():
    adapter = TapTapAdapter(httpx.Client())
    with pytest.raises(ValueError):
        adapter.parse_community_id("not a url")


def test_register_community_duplicate(db_session):
    adapter = FakeAdapter([_make_post()])
    register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)
    with pytest.raises(DuplicateCommunityError):
        register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)


def test_upsert_post_dedup(db_session):
    adapter = FakeAdapter([_make_post()])
    community = register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)
    p1, created1 = upsert_post(db_session, community.id, _make_post())
    p2, created2 = upsert_post(db_session, community.id, _make_post())
    assert created1 is True
    assert created2 is False
    assert p1.id == p2.id


def test_upsert_post_updates_recent_metrics(db_session):
    """近 3 天的帖子重复抓取时应更新点赞/回复数。"""
    adapter = FakeAdapter([_make_post()])
    community = register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)

    recent = FetchedPost(
        taptap_post_id="r1", title="t", content="c", author="a",
        published_at=now_cn() - timedelta(hours=2),
        reply_count=5, like_count=10, raw_url="https://example.com/p/r1",
    )
    _, created = upsert_post(db_session, community.id, recent)
    assert created is True

    updated = FetchedPost(
        taptap_post_id="r1", title="t", content="c", author="a",
        published_at=now_cn() - timedelta(hours=2),
        reply_count=99, like_count=123, raw_url="https://example.com/p/r1",
    )
    p2, created2 = upsert_post(db_session, community.id, updated)
    assert created2 is False
    assert p2.reply_count == 99
    assert p2.like_count == 123


def test_upsert_post_skips_stale_metrics(db_session):
    """超过 3 天的旧帖重复抓取时不更新（保持原值）。"""
    adapter = FakeAdapter([_make_post()])
    community = register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)

    stale = FetchedPost(
        taptap_post_id="s1", title="t", content="c", author="a",
        published_at=now_cn() - timedelta(days=10),
        reply_count=5, like_count=10, raw_url="https://example.com/p/s1",
    )
    _, created = upsert_post(db_session, community.id, stale)
    assert created is True

    refreshed = FetchedPost(
        taptap_post_id="s1", title="t", content="c", author="a",
        published_at=now_cn() - timedelta(days=10),
        reply_count=77, like_count=88, raw_url="https://example.com/p/s1",
    )
    p2, created2 = upsert_post(db_session, community.id, refreshed)
    assert created2 is False
    assert p2.reply_count == 5
    assert p2.like_count == 10


def test_rate_limiter_enforces_interval():
    rl = RateLimiter(min_interval_seconds=1.0)
    sleeps: list[float] = []
    rl.next_allowed("https://a.com/x", now=0.0)
    wait = rl.next_allowed("https://a.com/y", now=0.0)
    assert wait >= 1.0


def test_retry_with_backoff_succeeds_after_failures():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("boom")
        return "ok"

    result = retry_with_backoff(fn, max_retries=3, base_delay=0.0, sleep=lambda s: None)
    assert result == "ok"
    assert calls["n"] == 3


def test_retry_with_backoff_exhausts():
    def fn():
        raise RuntimeError("boom")

    with pytest.raises(MaxRetriesExceeded):
        retry_with_backoff(fn, max_retries=1, base_delay=0.0, sleep=lambda s: None)


def test_run_collection_success(db_session):
    posts = [_make_post("p1"), _make_post("p2")]
    adapter = FakeAdapter(posts)
    community = register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)
    rl = RateLimiter(min_interval_seconds=0.0)
    run = run_collection(db_session, community, adapter, rl, max_retries=1)
    assert run.fetched_count == 2
    assert run.new_count == 2
    assert run.failed_count == 0
    assert run.status.value == "success"


def test_run_collection_dedup(db_session):
    posts = [_make_post("p1"), _make_post("p2")]
    adapter = FakeAdapter(posts)
    community = register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)
    rl = RateLimiter(min_interval_seconds=0.0)
    run_collection(db_session, community, adapter, rl, max_retries=1)
    run2 = run_collection(db_session, community, adapter, rl, max_retries=1)
    assert run2.new_count == 0
    assert run2.fetched_count == 2


def test_run_collection_anti_crawl_at_list(db_session):
    adapter = FakeAdapter([_make_post()], anti_crawl_at=0)
    community = register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)
    rl = RateLimiter(min_interval_seconds=0.0)
    run = run_collection(db_session, community, adapter, rl, max_retries=1)
    assert run.status.value == "blocked"
    assert "anti-crawl" in run.error


def test_run_collection_records_collection_run(db_session):
    adapter = FakeAdapter([_make_post("p1")])
    community = register_community(db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter)
    rl = RateLimiter(min_interval_seconds=0.0)
    run = run_collection(db_session, community, adapter, rl, max_retries=1)
    assert run.started_at is not None
    assert run.ended_at is not None
    assert run.community_id == community.id
    assert run.fetched_count == 1
