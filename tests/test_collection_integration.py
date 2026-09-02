from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.collector.adapter import CommunityAdapter, FetchedPost
from app.collector.rate_limit import RateLimiter
from app.collector.service import register_community, run_collection
from app.core.db import get_engine, init_engine, create_all
from app.core.config import AppConfig, ServerConfig, CollectorConfig, AnalyzerConfig, DatabaseConfig, AIConfig
from app.core.models import Community, Post
from sqlmodel import Session, select


@pytest.fixture()
def db(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    config = AppConfig(
        server=ServerConfig(),
        collector=CollectorConfig(),
        analyzer=AnalyzerConfig(),
        database=DatabaseConfig(url=db_url),
        ai=AIConfig(base_url="http://localhost/v1", api_key="k", model="m"),
    )
    import app.core.db as dbmod
    dbmod._engine = None
    init_engine(config)
    create_all()
    yield get_engine()
    dbmod._engine = None


class FakeAdapter(CommunityAdapter):
    def __init__(self):
        self._discover_called = False
        self._group_id_returned = "162908"

    def parse_community_id(self, raw_url: str) -> str:
        return "app:139029"

    def is_anti_crawl_response(self, status_code: int, body_sample: str) -> bool:
        return False

    def fetch_post_list(self, community_id: str, limit: int, **kwargs) -> list[dict]:
        group_id = kwargs.get("group_id")
        if not group_id:
            self._discover_called = True
        return [
            {
                "taptap_post_id": f"m{i}",
                "raw_url": f"https://www.taptap.cn/moment/m{i}",
                "_moment": {"id_str": f"m{i}", "topic": {"id_str": f"t{i}", "title": f"标题{i}", "summary": "摘要"}, "group": {"id": 162908}},
                "group_id": "162908",
            }
            for i in range(3)
        ]

    def fetch_post_detail(self, post_ref: dict) -> FetchedPost:
        m = post_ref["_moment"]
        t = m.get("topic", {})
        return FetchedPost(
            taptap_post_id=post_ref["taptap_post_id"],
            title=t.get("title", ""),
            content=t.get("summary", ""),
            author="作者",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            reply_count=0,
            like_count=0,
            raw_url=post_ref["raw_url"],
            topic_id=t.get("id_str", ""),
            group_id=str(m.get("group", {}).get("id", "")),
        )


def test_run_collection_writes_group_id(db):
    with Session(db) as s:
        adapter = FakeAdapter()
        community = register_community(
            s, "https://www.taptap.cn/app/139029/topic",
            interval_seconds=3600, per_run_limit=5, adapter=adapter,
            name="test", platform="taptap",
        )
        assert community.platform_id == "139029"
        assert community.group_id is None

        rl = RateLimiter(min_interval_seconds=0)
        run = run_collection(s, community, adapter, rl, max_retries=1)
        assert run.status.value == "success"
        assert run.new_count == 3

        s.refresh(community)
        assert community.group_id == "162908"

        posts = s.exec(select(Post).where(Post.community_id == community.id)).all()
        assert len(posts) == 3
        for p in posts:
            assert p.topic_id.startswith("t")
            assert p.group_id == "162908"


def test_run_collection_reuses_group_id(db):
    with Session(db) as s:
        adapter = FakeAdapter()
        community = register_community(
            s, "https://www.taptap.cn/app/139029/topic",
            interval_seconds=3600, per_run_limit=5, adapter=adapter,
        )
        community.group_id = "162908"
        s.add(community)
        s.commit()

        rl = RateLimiter(min_interval_seconds=0)
        run_collection(s, community, adapter, rl, max_retries=1)
        assert adapter._discover_called is False
