from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.collector.adapter import CommunityAdapter, FetchedPost
from app.collector.service import register_community, upsert_post
from app.analyzer.parser import parse_analysis_json
from app.analyzer.service import persist_analysis_result
from app.core.db import _engine, init_engine, create_all
from app.core.config import AppConfig, ServerConfig, CollectorConfig, AnalyzerConfig, DatabaseConfig, AIConfig
from app.dashboard.server import create_app


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = AppConfig(
        server=ServerConfig(),
        collector=CollectorConfig(),
        analyzer=AnalyzerConfig(poll_interval_seconds=86400),
        database=DatabaseConfig(url=db_url),
        ai=AIConfig(base_url="http://localhost/v1", api_key="k", model="m"),
    )
    import app.core.db as dbmod
    dbmod._engine = None
    app = create_app(config)
    yield TestClient(app)
    import app.dashboard.server as srv
    srv._state.clear()


def _seed(api_client):
    pass


def test_health(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_communities_empty(api_client):
    r = api_client.get("/api/communities")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_register_community_invalid_url(api_client):
    r = api_client.post("/api/communities", json={"raw_url": "not a url", "interval_seconds": 60, "per_run_limit": 5})
    assert r.status_code == 400


def test_full_aggregation_flow(api_client, monkeypatch):
    from app.collector.taptap_adapter import TapTapAdapter

    r = api_client.post(
        "/api/communities",
        json={"raw_url": "https://www.taptap.cn/app/12345", "name": "Game", "interval_seconds": 60, "per_run_limit": 5},
    )
    assert r.status_code == 200, r.text
    community = r.json()
    cid = community["id"]

    from app.core.db import get_engine
    from sqlmodel import Session
    from app.core.models import Post
    from app.collector.adapter import FetchedPost

    with Session(get_engine()) as s:
        from app.core.models import Community
        c = s.get(Community, cid)
        for i in range(2):
            p, _ = upsert_post(s, c.id, FetchedPost(
                taptap_post_id=f"p{i}", title=f"title{i}", content="抽卡体验差 闪退 建议增加保底",
                author="u", published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                reply_count=0, like_count=0, raw_url=f"https://x/{i}",
            ))
            payload = parse_analysis_json(__import__("json").dumps({
                "topics": ["抽卡", "闪退"],
                "sentiment": "negative",
                "bugs": [{"summary": "闪退", "impact": "高"}],
                "suggestions": [{"summary": "增加保底", "category": "数值"}],
                "content_reviews": [{"subject": "角色A", "sentiment": "positive", "summary": "强"}],
            }))
            persist_analysis_result(s, p, payload)

    r = api_client.get(f"/api/communities/{cid}/sentiment")
    assert r.status_code == 200
    assert "series" in r.json()

    r = api_client.get(f"/api/communities/{cid}/topics")
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1

    r = api_client.get(f"/api/communities/{cid}/bugs-suggestions")
    assert r.status_code == 200
    assert len(r.json()["bugs"]) >= 1

    r = api_client.get(f"/api/communities/{cid}/content-reviews")
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1

    r = api_client.get("/api/insights/topic/posts", params={"community_id": cid, "keyword": "抽卡"})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2

    r = api_client.get(f"/api/communities/{cid}/runs")
    assert r.status_code == 200
    assert "items" in r.json()
