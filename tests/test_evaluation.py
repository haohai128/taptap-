from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.analyzer.parser import parse_analysis_json
from app.analyzer.service import persist_analysis_result
from app.collector.adapter import FetchedPost
from app.collector.service import upsert_post
from app.core.config import (
    AIConfig,
    AnalyzerConfig,
    AppConfig,
    CollectorConfig,
    DatabaseConfig,
    ServerConfig,
)
from app.core.db import get_engine
from app.core.models import Community, Post, Review, ReviewStatus
from app.dashboard.server import create_app
from app.analyzer.evaluation import (
    compute_accuracy,
    list_evaluation_posts,
    submit_review,
)


@pytest.fixture()
def api_client(tmp_path):
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


def _seed_two_posts(api_client):
    """注册社区并注入 2 篇带 AI 分析结果的帖子，返回 (cid, [post_id,...])。"""
    r = api_client.post(
        "/api/communities",
        json={"raw_url": "https://www.taptap.cn/app/12345", "name": "Game", "interval_seconds": 60, "per_run_limit": 5},
    )
    assert r.status_code == 200
    cid = r.json()["id"]

    with Session(get_engine()) as s:
        c = s.get(Community, cid)
        post_ids = []
        for i in range(2):
            p, _ = upsert_post(s, c.id, FetchedPost(
                taptap_post_id=f"ev-{i}", title=f"title{i}", content="平衡性差 闪退",
                author="u", published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                reply_count=0, like_count=0, raw_url=f"https://x/{i}",
            ))
            payload = parse_analysis_json(json.dumps({
                "topics": ["平衡性"],
                "sentiment": "negative",
                "bugs": [{"summary": "闪退", "impact": "高"}],
                "suggestions": [{"summary": "增加保底", "category": "数值"}],
                "content_reviews": [{"subject": "英雄A", "sentiment": "negative", "summary": "弱"}],
            }))
            persist_analysis_result(s, p, payload)
            post_ids.append(p.id)
    return cid, post_ids


# -------- 服务层测试 --------

def test_list_evaluation_posts_structure(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    with Session(get_engine()) as s:
        r = list_evaluation_posts(s, community_id=cid, status=None, page=1, page_size=20)
    assert r["total"] == 2
    assert len(r["items"]) == 2
    item = r["items"][0]
    assert "post" in item and "analysis" in item and "review" in item
    assert item["review"] is None
    assert item["analysis"]["sentiment"] == "negative"
    assert "topics" in item["analysis"]


def test_list_evaluation_posts_filter_unreviewed(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    with Session(get_engine()) as s:
        submit_review(s, post_ids[0], {"status": "correct"})
        unrev = list_evaluation_posts(s, community_id=cid, status="unreviewed")
        rev = list_evaluation_posts(s, community_id=cid, status="reviewed")
    assert unrev["total"] == 1
    assert rev["total"] == 1


def test_list_evaluation_posts_filter_incorrect(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    with Session(get_engine()) as s:
        submit_review(s, post_ids[0], {"status": "incorrect", "sentiment_correct": False})
        submit_review(s, post_ids[1], {"status": "correct"})
        incor = list_evaluation_posts(s, community_id=cid, status="incorrect")
    assert incor["total"] == 1
    assert incor["items"][0]["post"]["id"] == post_ids[0]


def test_submit_review_insert_then_overwrite(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    with Session(get_engine()) as s:
        r1 = submit_review(s, post_ids[0], {"status": "correct"})
        assert r1.id is not None
        assert r1.status == ReviewStatus.CORRECT.value
        r2 = submit_review(s, post_ids[0], {"status": "partial", "sentiment_correct": False, "corrected_sentiment": "neutral"})
        assert r2.id == r1.id
        assert r2.status == ReviewStatus.PARTIAL.value
        assert r2.sentiment_correct is False
        assert r2.corrected_sentiment == "neutral"


def test_compute_accuracy_no_reviews_returns_zero(api_client):
    cid, _ = _seed_two_posts(api_client)
    with Session(get_engine()) as s:
        acc = compute_accuracy(s, community_id=cid)
    assert acc["total"] == 0
    for k in ["sentiment_accuracy", "bugs_accuracy", "suggestions_accuracy", "topics_accuracy", "content_reviews_accuracy", "overall_accuracy"]:
        assert acc[k] == 0.0


def test_compute_accuracy_with_reviews(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    with Session(get_engine()) as s:
        submit_review(s, post_ids[0], {"status": "correct"})
        submit_review(s, post_ids[1], {"status": "incorrect", "sentiment_correct": False, "bugs_correct": False})
        acc = compute_accuracy(s, community_id=cid)
    assert acc["total"] == 2
    assert acc["correct_count"] == 1
    assert acc["incorrect_count"] == 1
    assert acc["sentiment_accuracy"] == 50.0
    assert acc["bugs_accuracy"] == 50.0
    assert acc["topics_accuracy"] == 100.0
    assert acc["overall_accuracy"] == 50.0


# -------- API 层测试 --------

def test_api_evaluation_posts_default(api_client):
    cid, _ = _seed_two_posts(api_client)
    r = api_client.get("/api/evaluation/posts", params={"community_id": cid})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_api_evaluation_posts_filter_status(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    api_client.post(f"/api/evaluation/posts/{post_ids[0]}/review", json={"status": "correct"})
    r = api_client.get("/api/evaluation/posts", params={"community_id": cid, "status": "unreviewed"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    r = api_client.get("/api/evaluation/posts", params={"community_id": cid, "status": "reviewed"})
    assert r.json()["total"] == 1
    r = api_client.get("/api/evaluation/posts", params={"community_id": cid, "status": "incorrect"})
    assert r.json()["total"] == 0


def test_api_submit_review_correct(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    r = api_client.post(f"/api/evaluation/posts/{post_ids[0]}/review", json={"status": "correct"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "correct"
    assert body["post_id"] == post_ids[0]
    assert body["sentiment_correct"] is True

    r = api_client.get("/api/evaluation/posts", params={"community_id": cid, "status": "reviewed"})
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["review"]["status"] == "correct"


def test_api_submit_review_partial_with_corrections(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    payload = {
        "status": "partial",
        "sentiment_correct": False,
        "bugs_correct": False,
        "corrected_sentiment": "neutral",
        "corrected_bugs": [{"summary": "修正BUG", "impact": "低"}],
    }
    r = api_client.post(f"/api/evaluation/posts/{post_ids[0]}/review", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "partial"
    assert body["sentiment_correct"] is False
    assert body["corrected_sentiment"] == "neutral"
    assert body["corrected_bugs"] == [{"summary": "修正BUG", "impact": "低"}]


def test_api_submit_review_invalid_status(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    r = api_client.post(f"/api/evaluation/posts/{post_ids[0]}/review", json={"status": "bogus"})
    assert r.status_code == 400


def test_api_submit_review_post_not_found(api_client):
    r = api_client.post("/api/evaluation/posts/99999/review", json={"status": "correct"})
    assert r.status_code == 404


def test_api_evaluation_accuracy_empty(api_client):
    cid, _ = _seed_two_posts(api_client)
    r = api_client.get("/api/evaluation/accuracy", params={"community_id": cid})
    assert r.status_code == 200
    data = r.json()
    expected_keys = {
        "total", "correct_count", "incorrect_count", "partial_count",
        "sentiment_accuracy", "bugs_accuracy", "suggestions_accuracy",
        "topics_accuracy", "content_reviews_accuracy", "overall_accuracy",
    }
    assert expected_keys.issubset(set(data.keys()))
    assert data["total"] == 0
    assert data["overall_accuracy"] == 0.0


def test_api_evaluation_accuracy_with_data(api_client):
    cid, post_ids = _seed_two_posts(api_client)
    api_client.post(f"/api/evaluation/posts/{post_ids[0]}/review", json={"status": "correct"})
    api_client.post(f"/api/evaluation/posts/{post_ids[1]}/review", json={"status": "incorrect", "sentiment_correct": False})
    r = api_client.get("/api/evaluation/accuracy", params={"community_id": cid})
    data = r.json()
    assert data["total"] == 2
    assert data["sentiment_accuracy"] == 50.0
    assert data["overall_accuracy"] == 50.0


def test_api_evaluation_pagination(api_client):
    cid, _ = _seed_two_posts(api_client)
    r = api_client.get("/api/evaluation/posts", params={"community_id": cid, "page": 1, "page_size": 1})
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["page"] == 1
    assert data["page_size"] == 1
