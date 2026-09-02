from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.analyzer.evaluation import submit_review
from app.analyzer.parser import parse_analysis_json
from app.analyzer.service import persist_analysis_result, record_analysis_failure
from app.collector import platform_state
from app.collector.adapter import (
    AntiCrawlError,
    CollectorErrorType,
    CommunityAdapter,
    CommunityNotAccessibleError,
    FetchedPost,
    classify_http_status,
)
from app.collector.platform_rate_limit import PlatformRateLimiter
from app.collector.service import run_collection, upsert_post
from app.collector.retry import MaxRetriesExceeded
from app.core.config import (
    AIConfig,
    AnalyzerConfig,
    AppConfig,
    CollectorConfig,
    DatabaseConfig,
    PlatformConfig,
    ServerConfig,
    load_config,
)
from app.core.db import get_engine
from app.core.models import (
    AnalysisAttempt,
    AnalysisResult,
    CollectionRun,
    CollectionRunStatus,
    Community,
    Post,
    PostStatus,
)
from app.dashboard.server import create_app


# -------- 风控识别层 --------

def test_classify_http_status_all_codes():
    assert classify_http_status(403) == CollectorErrorType.BLOCKED
    assert classify_http_status(412) == CollectorErrorType.BLOCKED
    assert classify_http_status(429) == CollectorErrorType.RATE_LIMITED
    assert classify_http_status(401) == CollectorErrorType.AUTH_EXPIRED
    assert classify_http_status(200) is None
    assert classify_http_status(404) is None
    assert classify_http_status(500) is None


class _DummyAdapter(CommunityAdapter):
    def parse_community_id(self, raw_url): return "app:1"
    def fetch_post_list(self, community_id, limit): return []
    def fetch_post_detail(self, post_ref): return None
    def is_anti_crawl_response(self, status_code, body_sample): return False


def test_classify_response_403():
    d = _DummyAdapter()
    r = httpx.Response(403, text="forbidden")
    assert d.classify_response(response=r) == CollectorErrorType.BLOCKED


def test_classify_response_412():
    d = _DummyAdapter()
    r = httpx.Response(412, text="风控")
    assert d.classify_response(response=r) == CollectorErrorType.BLOCKED


def test_classify_response_429():
    d = _DummyAdapter()
    r = httpx.Response(429, text="too many")
    assert d.classify_response(response=r) == CollectorErrorType.RATE_LIMITED


def test_classify_response_401():
    d = _DummyAdapter()
    r = httpx.Response(401, text="unauthorized")
    assert d.classify_response(response=r) == CollectorErrorType.AUTH_EXPIRED


def test_classify_response_200_captcha():
    d = _DummyAdapter()
    r = httpx.Response(200, text="请输入验证码继续访问")
    assert d.classify_response(response=r) == CollectorErrorType.BLOCKED


def test_classify_response_200_normal():
    d = _DummyAdapter()
    r = httpx.Response(200, text="正常内容")
    assert d.classify_response(response=r) is None


def test_classify_response_500_http_error():
    d = _DummyAdapter()
    r = httpx.Response(500, text="server error")
    assert d.classify_response(response=r) == CollectorErrorType.HTTP_ERROR


def test_classify_response_timeout():
    d = _DummyAdapter()
    assert d.classify_response(exception=httpx.ConnectTimeout("t")) == CollectorErrorType.NETWORK_ERROR
    assert d.classify_response(exception=httpx.ConnectError("e")) == CollectorErrorType.NETWORK_ERROR


def test_classify_response_404_not_anti():
    d = _DummyAdapter()
    r = httpx.Response(404, text="not found")
    assert d.classify_response(response=r) == CollectorErrorType.HTTP_ERROR


# -------- PlatformRateLimiter --------

def test_platform_rate_limiter_isolation():
    rl = PlatformRateLimiter(default_min_interval=0, default_backoff_factor=2.0, default_backoff_cap=10)
    rl.record_failure("other", CollectorErrorType.RATE_LIMITED)
    assert rl.is_in_backoff("other") is True
    assert rl.is_in_backoff("taptap") is False


def test_platform_rate_limiter_backoff_blocked():
    rl = PlatformRateLimiter(default_backoff_cap=10)
    d = rl.record_failure("other", CollectorErrorType.BLOCKED)
    assert d == 10


def test_platform_rate_limiter_exponential():
    rl = PlatformRateLimiter(default_min_interval=0, default_backoff_factor=2.0, default_backoff_cap=100)
    d1 = rl.record_failure("taptap", CollectorErrorType.NETWORK_ERROR)
    d2 = rl.record_failure("taptap", CollectorErrorType.NETWORK_ERROR)
    assert d2 > d1


def test_platform_rate_limiter_success_resets():
    rl = PlatformRateLimiter(default_min_interval=0)
    rl.record_failure("taptap", CollectorErrorType.NETWORK_ERROR)
    rl.record_success("taptap")
    assert rl.get_state("taptap")["consecutive_errors"] == 0
    assert rl.is_in_backoff("taptap") is False


# -------- PlatformConfig --------

def test_platform_config_defaults():
    c = load_config(require_ai=False)
    assert c.platforms == {}


def test_platform_config_override(tmp_path):
    import yaml
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump({"platforms": {"other": {"min_request_interval_seconds": 5, "max_retries": 2}}}))
    c = load_config(str(p), require_ai=False)
    assert c.platforms["other"].min_request_interval_seconds == 5.0
    assert c.platforms["other"].max_retries == 2
    assert "taptap" not in c.platforms


# -------- platform_state --------

def test_platform_state_isolation():
    platform_state.reset_platform_state()
    platform_state.update_platform_state("other", platform_state.STATUS_BLOCKED, error="412")
    platform_state.update_platform_state("taptap", platform_state.STATUS_NORMAL)
    states = platform_state.get_platform_states()
    assert states["other"]["status"] == "blocked"
    assert states["taptap"]["status"] == "normal"
    assert "third" not in states


# -------- run_collection 风控短路 --------

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
    platform_state.reset_platform_state()


def _make_community(session, platform="taptap", name="Game"):
    c = Community(
        taptap_id=f"app:{name}", name=name, raw_url="https://x", platform=platform,
        platform_id=name, enabled=True, interval_seconds=60, per_run_limit=5,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


class _MockAdapter(CommunityAdapter):
    """可注入 fetch 行为的 mock adapter。"""
    def __init__(self, platform="taptap", list_exc=None, list_items=None, detail_exc=None):
        self._platform = platform
        self._list_exc = list_exc
        self._list_items = list_items or []
        self._detail_exc = detail_exc
    def parse_community_id(self, raw_url): return f"app:x"
    def fetch_post_list(self, community_id, limit, **kw):
        if self._list_exc:
            raise self._list_exc
        return self._list_items
    def fetch_post_detail(self, post_ref):
        if self._detail_exc:
            raise self._detail_exc
        return FetchedPost(taptap_post_id=post_ref["taptap_post_id"], title="t", content="c", author="a",
                           published_at=datetime(2024,1,1,tzinfo=timezone.utc), reply_count=0, like_count=0,
                           raw_url=post_ref["raw_url"])
    def is_anti_crawl_response(self, status_code, body_sample): return False


def test_run_collection_412_blocked(api_client):
    from app.collector.rate_limit import RateLimiter
    with Session(get_engine()) as s:
        c = _make_community(s, platform="other")
        adapter = _MockAdapter(list_exc=AntiCrawlError("412 风控"))
        rl = RateLimiter(min_interval_seconds=0)
        run = run_collection(s, c, adapter, rl, max_retries=1)
        assert run.status == CollectionRunStatus.BLOCKED
        assert run.error_type == CollectorErrorType.BLOCKED.value
        # 平台状态隔离：other blocked，taptap 未受影响
        states = platform_state.get_platform_states()
        assert states.get("other", {}).get("status") == "blocked"


def test_run_collection_network_error(api_client):
    from app.collector.rate_limit import RateLimiter
    with Session(get_engine()) as s:
        c = _make_community(s, platform="taptap")
        adapter = _MockAdapter(list_exc=httpx.ConnectTimeout("timeout"))
        rl = RateLimiter(min_interval_seconds=0)
        run = run_collection(s, c, adapter, rl, max_retries=1)
        assert run.status == CollectionRunStatus.NETWORK_ERROR
        assert run.error_type == CollectorErrorType.NETWORK_ERROR.value


def test_run_collection_auth_expired(api_client):
    from app.collector.rate_limit import RateLimiter
    with Session(get_engine()) as s:
        c = _make_community(s, platform="taptap")
        # 用普通 Exception 模拟，mock classify 返回 auth_expired
        adapter = _MockAdapter(list_exc=Exception("401 unauthorized"))
        adapter.classify_response = lambda response=None, exception=None: CollectorErrorType.AUTH_EXPIRED if exception else None
        rl = RateLimiter(min_interval_seconds=0)
        run = run_collection(s, c, adapter, rl, max_retries=1)
        assert run.status == CollectionRunStatus.AUTH_EXPIRED


def test_run_collection_5xx_http_error_finite_retry(api_client):
    from app.collector.rate_limit import RateLimiter
    with Session(get_engine()) as s:
        c = _make_community(s, platform="taptap")
        adapter = _MockAdapter(list_exc=Exception("500 server error"))
        adapter.classify_response = lambda response=None, exception=None: CollectorErrorType.HTTP_ERROR if exception else None
        rl = RateLimiter(min_interval_seconds=0)
        run = run_collection(s, c, adapter, rl, max_retries=2)
        # http_error 不在 _ERROR_TYPE_TO_RUN_STATUS，降级为 failed
        assert run.status == CollectionRunStatus.FAILED


def test_run_collection_success(api_client):
    from app.collector.rate_limit import RateLimiter
    with Session(get_engine()) as s:
        c = _make_community(s, platform="taptap")
        items = [{"taptap_post_id": "p1", "raw_url": "https://x/1", "_moment": {}}]
        adapter = _MockAdapter(list_items=items)
        rl = RateLimiter(min_interval_seconds=0)
        run = run_collection(s, c, adapter, rl, max_retries=1)
        assert run.status == CollectionRunStatus.SUCCESS
        assert run.new_count == 1
        states = platform_state.get_platform_states()
        assert states.get("taptap", {}).get("status") == "normal"


# -------- AI 分析失败容错 --------

def test_record_analysis_failure_retryable_then_abandoned(api_client):
    with Session(get_engine()) as s:
        c = _make_community(s)
        post, _ = upsert_post(s, c.id, FetchedPost(
            taptap_post_id="ai-fail-1", title="t", content="c", author="a",
            published_at=datetime(2024,1,1,tzinfo=timezone.utc), reply_count=0, like_count=0, raw_url="https://x",
        ))
        # 首次失败：retryable
        skip = record_analysis_failure(s, post, "AI timeout", max_attempts=3)
        assert skip is False
        att = s.exec(select(AnalysisAttempt).where(AnalysisAttempt.post_id == post.id)).first()
        assert att.status == "retryable"
        assert post.status == PostStatus.PENDING
        # 第二次失败：retryable
        skip = record_analysis_failure(s, post, "AI timeout 2", max_attempts=3)
        assert skip is False
        # 第三次失败：abandoned + post failed
        skip = record_analysis_failure(s, post, "AI timeout 3", max_attempts=3)
        assert skip is True
        s.refresh(att)
        s.refresh(post)
        assert att.status == "abandoned"
        assert post.status == PostStatus.FAILED


def test_ai_original_result_not_overwritten_by_review(api_client):
    with Session(get_engine()) as s:
        c = _make_community(s)
        post, _ = upsert_post(s, c.id, FetchedPost(
            taptap_post_id="ai-orig-1", title="t", content="c", author="a",
            published_at=datetime(2024,1,1,tzinfo=timezone.utc), reply_count=0, like_count=0, raw_url="https://x",
        ))
        payload = parse_analysis_json(json.dumps({"sentiment": "negative", "sentiment_reason": "原AI判断"}))
        persist_analysis_result(s, post, payload)
        # 提交人工评估
        submit_review(s, post.id, {"status": "incorrect", "sentiment_correct": False, "corrected_sentiment": "positive"})
        # AI 原始结果不应被改
        ar = s.exec(select(AnalysisResult).where(AnalysisResult.post_id == post.id)).first()
        assert ar.sentiment == "negative"
        assert ar.sentiment_reason == "原AI判断"


# -------- Dashboard API --------

def test_api_platforms_status(api_client):
    with Session(get_engine()) as s:
        c = _make_community(s, platform="taptap")
        items = [{"taptap_post_id": "ps-1", "raw_url": "https://x/1", "_moment": {}}]
        adapter = _MockAdapter(list_items=items)
        from app.collector.rate_limit import RateLimiter
        run_collection(s, c, adapter, RateLimiter(min_interval_seconds=0), max_retries=1)
    r = api_client.get("/api/platforms/status")
    assert r.status_code == 200
    data = r.json()
    items_out = data["items"]
    assert len(items_out) == 1
    taptap = [p for p in items_out if p["platform"] == "taptap"][0]
    assert taptap["last_run"] is not None
    assert taptap["last_run"]["status"] == "success"
