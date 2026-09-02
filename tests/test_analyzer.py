from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.analyzer.parser import (
    AnalysisParseError,
    parse_analysis_json,
    payload_to_db_json,
)
from app.analyzer.service import (
    fetch_pending_posts,
    persist_analysis_result,
    record_analysis_failure,
    reset_posts_for_reanalysis,
)
from app.analyzer.aggregation import (
    bugs_and_suggestions,
    content_reviews,
    sentiment_trend,
    topic_heat,
)
from app.analyzer.analyzer import SinglePostAnalyzer
from app.collector.adapter import FetchedPost
from app.collector.service import register_community, upsert_post
from app.collector.taptap_adapter import TapTapAdapter
from app.core.models import AnalysisResult, Post, PostStatus
import httpx


class StubOpenAI:
    def __init__(self, payload: dict):
        self._payload = payload

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, content):
                self.message = _Msg(content)

        class _Resp:
            def __init__(self, content):
                self.choices = [_Choice(content)]

        self._resp = _Resp(json.dumps(self._payload, ensure_ascii=False))

        class _Completions:
            def __init__(self, outer):
                self._outer = outer

            def create(self, **kwargs):
                return self._outer._resp

        self.chat = type("C", (), {"completions": _Completions(self)})()


def _make_post_in_db(db_session, pid="p1", title="标题", content="正文", published_at=None):
    adapter = TapTapAdapter(httpx.Client())
    community = register_community(
        db_session, "https://taptap.cn/app/1", interval_seconds=60, per_run_limit=5, adapter=adapter
    )
    fetched = FetchedPost(
        taptap_post_id=pid, title=title, content=content, author="a",
        published_at=published_at or datetime(2024, 1, 1), reply_count=0, like_count=0,
        raw_url="https://example.com/p/1",
    )
    post, _ = upsert_post(db_session, community.id, fetched)
    return community, post


def test_parser_valid_full():
    raw = json.dumps({
        "topics": ["抽卡", "数值"],
        "sentiment": "negative",
        "sentiment_reason": "玩家抱怨爆率",
        "bugs": [{"summary": "闪退", "impact": "无法进入"}],
        "suggestions": [{"summary": "增加保底", "category": "数值调整"}],
        "content_reviews": [{"subject": "角色A", "sentiment": "positive", "summary": "强"}],
    })
    payload = parse_analysis_json(raw)
    assert payload.sentiment == "negative"
    assert len(payload.bugs) == 1
    assert payload.bugs[0].summary == "闪退"
    assert len(payload.suggestions) == 1
    assert payload.content_reviews[0].subject == "角色A"


def test_parser_strips_code_fences():
    raw = "```json\n" + json.dumps({"sentiment": "neutral"}) + "\n```"
    payload = parse_analysis_json(raw)
    assert payload.sentiment == "neutral"


def test_parser_invalid_sentiment_falls_back():
    payload = parse_analysis_json(json.dumps({"sentiment": "happy"}))
    assert payload.sentiment == "unknown"


def test_parser_empty_arrays():
    payload = parse_analysis_json(json.dumps({}))
    assert payload.topics == []
    assert payload.bugs == []
    assert payload.suggestions == []
    assert payload.content_reviews == []
    assert payload.sentiment == "unknown"


def test_parser_invalid_json_raises():
    with pytest.raises(AnalysisParseError):
        parse_analysis_json("not json")


def test_payload_to_db_json_roundtrip():
    payload = parse_analysis_json(json.dumps({
        "topics": ["t1"],
        "sentiment": "positive",
        "bugs": [{"summary": "b", "impact": "i"}],
    }))
    fields = payload_to_db_json(payload)
    assert json.loads(fields["topics_json"]) == ["t1"]
    assert json.loads(fields["bugs_json"]) == [{"summary": "b", "impact": "i"}]


def test_persist_analysis_result_updates_status(db_session):
    community, post = _make_post_in_db(db_session)
    payload = parse_analysis_json(json.dumps({"sentiment": "positive", "topics": ["t"]}))
    result = persist_analysis_result(db_session, post, payload)
    assert result.post_id == post.id
    db_session.refresh(post)
    assert post.status == PostStatus.ANALYZED


def test_record_analysis_failure_skips_after_max(db_session):
    community, post = _make_post_in_db(db_session)
    skip1 = record_analysis_failure(db_session, post, "err", max_attempts=2)
    assert skip1 is False
    skip2 = record_analysis_failure(db_session, post, "err2", max_attempts=2)
    assert skip2 is True
    db_session.refresh(post)
    assert post.status == PostStatus.FAILED


def test_reset_posts_for_reanalysis(db_session):
    community, post = _make_post_in_db(db_session)
    post.status = PostStatus.ANALYZED
    db_session.add(post)
    db_session.commit()
    n = reset_posts_for_reanalysis(db_session, community.id)
    assert n == 1
    db_session.refresh(post)
    assert post.status == PostStatus.PENDING


def test_fetch_pending_posts_returns_only_pending(db_session):
    community, post = _make_post_in_db(db_session, pid="p1")
    post2, _ = upsert_post(db_session, community.id, FetchedPost(
        taptap_post_id="p2", title="t", content="c", author="a",
        published_at=datetime(2024, 1, 2), reply_count=0, like_count=0,
        raw_url="https://example.com/p/2"))
    post2.status = PostStatus.ANALYZED
    db_session.add(post2)
    db_session.commit()
    pending = fetch_pending_posts(db_session, community.id, batch_size=10)
    assert len(pending) == 1
    assert pending[0].taptap_post_id == "p1"


def test_single_post_analyzer_success():
    payload = {"sentiment": "positive", "topics": ["t"]}
    client = StubOpenAI(payload)
    analyzer = SinglePostAnalyzer(client, model="m", use_json_mode=True)
    result = analyzer.analyze("title", "content")
    assert result.sentiment == "positive"


def test_single_post_analyzer_parse_retry_then_fail():
    class _BadClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    class _M: content = "not valid json"
                    class _C: message = _M()
                    class _R: choices = [_C()]
                    return _R()
    analyzer = SinglePostAnalyzer(_BadClient, model="m", use_json_mode=True, parse_retries=1)
    from app.analyzer.analyzer import AnalysisError
    with pytest.raises(AnalysisError):
        analyzer.analyze("t", "c")


def test_aggregation_sentiment_trend(db_session):
    community, post = _make_post_in_db(db_session, pid="p1", published_at=datetime(2024, 1, 1))
    payload = parse_analysis_json(json.dumps({"sentiment": "positive"}))
    persist_analysis_result(db_session, post, payload)
    trend = sentiment_trend(db_session, community.id)
    assert "days" in trend
    assert any(any(pt["count"] > 0 for pt in pts) for pts in trend["series"].values())


def test_aggregation_topic_heat(db_session):
    community, post = _make_post_in_db(db_session, pid="p1")
    payload = parse_analysis_json(json.dumps({"topics": ["抽卡", "闪退"]}))
    persist_analysis_result(db_session, post, payload)
    heat = topic_heat(db_session, community.id)
    assert len(heat) == 2
    assert heat[0]["count"] == 1


def test_aggregation_bugs_and_suggestions(db_session):
    community, post = _make_post_in_db(db_session, pid="p1")
    payload = parse_analysis_json(json.dumps({
        "bugs": [{"summary": "闪退", "impact": "高"}],
        "suggestions": [{"summary": "保底", "category": "数值"}],
    }))
    persist_analysis_result(db_session, post, payload)
    out = bugs_and_suggestions(db_session, community.id)
    assert len(out["bugs"]) == 1
    assert out["bugs"][0]["post_count"] == 1
    assert len(out["suggestions"]) == 1


def test_aggregation_content_reviews(db_session):
    community, post = _make_post_in_db(db_session, pid="p1")
    payload = parse_analysis_json(json.dumps({
        "content_reviews": [{"subject": "角色A", "sentiment": "positive", "summary": "强"}],
    }))
    persist_analysis_result(db_session, post, payload)
    reviews = content_reviews(db_session, community.id)
    assert len(reviews) == 1
    assert reviews[0]["subject"] == "角色A"
    assert reviews[0]["positive"] == 1
