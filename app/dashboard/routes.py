from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.models import CollectionRun, Community, Post, AnalysisResult, Review, Alert
from app.core.tz import iso_cn
from app.analyzer.aggregation import (
    bugs_and_suggestions,
    content_reviews,
    dashboard_summary,
    platform_overview,
    sentiment_proportion,
    sentiment_trend,
    time_distribution,
    topic_heat,
    wordcloud,
)
from app.analyzer.service import reset_posts_for_reanalysis
from app.analyzer.watchdog import (
    add_keyword,
    content_library,
    create_alert,
    create_briefing,
    delete_keyword,
    generate_alerts_for_negative,
    list_alerts,
    list_briefings,
    list_keywords,
    negative_library,
    resolve_alert,
    toggle_keyword,
)
from app.collector.registry import get_adapter, supported_platforms
from app.collector.service import DuplicateCommunityError, register_community, run_collection
from app.collector.taptap_adapter import TapTapAdapter
from app.analyzer.evaluation import (
    compute_accuracy as eval_compute_accuracy,
    list_evaluation_posts as eval_list_posts,
    submit_review as eval_submit_review,
)
import httpx

router = APIRouter()


class CommunityCreate(BaseModel):
    raw_url: str
    name: str = ""
    platform: str = "taptap"
    interval_seconds: int = 3600
    per_run_limit: int = 50


class KeywordCreate(BaseModel):
    word: str
    category: str = "track"


def _community_to_out(c: Community, last_run: Optional[CollectionRun] = None) -> dict:
    return {
        "id": c.id,
        "taptap_id": c.taptap_id,
        "name": c.name,
        "raw_url": c.raw_url,
        "platform": c.platform,
        "enabled": c.enabled,
        "collect_status": c.collect_status,
        "interval_seconds": c.interval_seconds,
        "per_run_limit": c.per_run_limit,
        "created_at": iso_cn(c.created_at),
        "last_run": _run_summary(last_run) if last_run else None,
    }


def _run_summary(r: Optional[CollectionRun]) -> Optional[dict]:
    if r is None:
        return None
    return {
        "id": r.id,
        "started_at": iso_cn(r.started_at),
        "ended_at": iso_cn(r.ended_at),
        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        "fetched_count": r.fetched_count,
        "new_count": r.new_count,
        "failed_count": r.failed_count,
        "error": r.error,
    }


def _last_run_for(session: Session, community_id: int) -> Optional[CollectionRun]:
    return session.exec(
        select(CollectionRun)
        .where(CollectionRun.community_id == community_id)
        .order_by(CollectionRun.started_at.desc())
    ).first()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/settings")
def get_settings():
    from app.dashboard.server import _state
    config = _state.get("config")
    ai = config.ai if config and config.ai else None
    return {
        "ai_model": ai.model if ai else None,
        "ai_base_url": ai.base_url if ai else None,
        "database": "sqlite",
        "server": f"{config.server.host}:{config.server.port}" if config else None,
        "collector_interval_default": config.collector.schedule_interval_seconds_default if config else None,
        "analyzer_poll_interval": config.analyzer.poll_interval_seconds if config else None,
    }


@router.get("/platforms")
def platforms():
    return {"items": supported_platforms()}


@router.get("/dashboard/summary")
def get_dashboard_summary(session: Session = Depends(get_session)):
    return dashboard_summary(session)


# -------- 社区 --------

@router.get("/communities")
def list_communities(session: Session = Depends(get_session)):
    communities = session.exec(select(Community)).all()
    out = []
    for c in communities:
        out.append(_community_to_out(c, _last_run_for(session, c.id)))
    return {"items": out}


@router.post("/communities")
def create_community(payload: CommunityCreate, session: Session = Depends(get_session)):
    adapter = get_adapter(payload.platform)
    try:
        community = register_community(
            session,
            payload.raw_url,
            interval_seconds=payload.interval_seconds,
            per_run_limit=payload.per_run_limit,
            adapter=adapter,
            name=payload.name,
            platform=payload.platform,
        )
    except DuplicateCommunityError as exc:
        raise HTTPException(status_code=409, detail=f"社区已存在: {exc.existing.taptap_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"无效社区链接: {exc}")

    from app.dashboard.runtime import schedule_community_after_register

    try:
        schedule_community_after_register(community)
    except Exception:
        pass
    return _community_to_out(community)


@router.get("/communities/{community_id}/runs")
def list_runs(community_id: int, session: Session = Depends(get_session)):
    runs = session.exec(
        select(CollectionRun)
        .where(CollectionRun.community_id == community_id)
        .order_by(CollectionRun.started_at.desc())
    ).all()
    return {"items": [_run_summary(r) for r in runs]}


@router.delete("/communities/{community_id}")
def delete_community(community_id: int, session: Session = Depends(get_session)):
    from app.dashboard.runtime import unschedule_community_after_delete
    from app.collector import cancel_token

    community = session.get(Community, community_id)
    if not community:
        raise HTTPException(status_code=404, detail="community not found")

    # 先停止调度任务和采集
    try:
        unschedule_community_after_delete(community_id)
    except Exception:
        pass
    cancel_token.request_stop(community_id)

    # 级联删除关联数据
    posts = session.exec(select(Post).where(Post.community_id == community_id)).all()
    post_ids = [p.id for p in posts]
    if post_ids:
        for pid in post_ids:
            ars = session.exec(select(AnalysisResult).where(AnalysisResult.post_id == pid)).all()
            for ar in ars:
                session.delete(ar)
            reviews = session.exec(select(Review).where(Review.post_id == pid)).all()
            for rv in reviews:
                session.delete(rv)
        for p in posts:
            session.delete(p)

    # 删除采集记录
    runs = session.exec(select(CollectionRun).where(CollectionRun.community_id == community_id)).all()
    for r in runs:
        session.delete(r)

    # 删除告警
    alerts = session.exec(select(Alert).where(Alert.community_id == community_id)).all()
    for a in alerts:
        session.delete(a)

    session.delete(community)
    session.commit()
    return {"status": "deleted"}


@router.post("/communities/{community_id}/collect-now")
def collect_now(community_id: int, session: Session = Depends(get_session)):
    from app.dashboard.runtime import trigger_collect_now

    community = session.get(Community, community_id)
    if not community:
        raise HTTPException(status_code=404, detail="community not found")
    if community.collect_status == "stopped":
        raise HTTPException(status_code=409, detail="该社区采集已停止，请先启用采集")
    trigger_collect_now(community_id)
    return {"status": "scheduled"}


@router.post("/communities/{community_id}/stop-collection")
def stop_collection(community_id: int, session: Session = Depends(get_session)):
    from app.collector import cancel_token

    community = session.get(Community, community_id)
    if not community:
        raise HTTPException(status_code=404, detail="community not found")
    community.collect_status = "stopped"
    session.add(community)
    session.commit()
    session.refresh(community)
    cancel_token.request_stop(community_id)
    return {"collect_status": "stopped"}


@router.post("/communities/{community_id}/start-collection")
def start_collection(community_id: int, session: Session = Depends(get_session)):
    from app.collector import cancel_token

    community = session.get(Community, community_id)
    if not community:
        raise HTTPException(status_code=404, detail="community not found")
    community.collect_status = "enabled"
    session.add(community)
    session.commit()
    session.refresh(community)
    cancel_token.clear_stop(community_id)
    return {"collect_status": "enabled"}


@router.post("/communities/{community_id}/reanalyze")
def reanalyze(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    n = reset_posts_for_reanalysis(session, community_id, since=since, until=until)
    return {"reset_count": n}


# -------- 图表分析 --------

@router.get("/communities/{community_id}/sentiment")
def get_sentiment(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    return sentiment_trend(session, community_id, since=since, until=until)


@router.get("/communities/{community_id}/sentiment-proportion")
def get_sentiment_proportion(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    return {"items": sentiment_proportion(session, community_id, since=since, until=until)}


@router.get("/communities/{community_id}/time-distribution")
def get_time_distribution(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    return {"items": time_distribution(session, community_id, since=since, until=until)}


@router.get("/communities/{community_id}/topics")
def get_topics(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    top_n: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"items": topic_heat(session, community_id, since=since, until=until, top_n=top_n)}


@router.get("/communities/{community_id}/wordcloud")
def get_wordcloud(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    top_n: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"items": wordcloud(session, community_id, since=since, until=until, top_n=top_n)}


@router.get("/communities/{community_id}/bugs-suggestions")
def get_bugs_suggestions(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    return bugs_and_suggestions(session, community_id, since=since, until=until)


@router.get("/communities/{community_id}/content-reviews")
def get_content_reviews(
    community_id: int,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    return {"items": content_reviews(session, community_id, since=since, until=until)}


@router.get("/platform-overview")
def get_platform_overview(
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    return {"items": platform_overview(session, since=since, until=until)}


@router.get("/platforms/status")
def get_platforms_status(session: Session = Depends(get_session)):
    """返回各平台当前采集状态（内存实时 + DB 最近一次采集摘要）。"""
    from app.collector import platform_state
    from app.core.models import CollectionRun

    mem_states = platform_state.get_platform_states()
    # 按 platform 聚合最近一次 CollectionRun
    platforms = ["taptap"]
    out = []
    for pf in platforms:
        last_run = session.exec(
            select(CollectionRun)
            .join(Community, Community.id == CollectionRun.community_id)
            .where(Community.platform == pf)
            .order_by(CollectionRun.started_at.desc())
        ).first()
        mem = mem_states.get(pf, {})
        out.append({
            "platform": pf,
            "status": mem.get("status", platform_state.STATUS_NORMAL),
            "error": mem.get("error", ""),
            "last_run_at": mem.get("last_run_at", ""),
            "last_run": {
                "id": last_run.id,
                "status": last_run.status.value if hasattr(last_run.status, "value") else last_run.status,
                "error_type": last_run.error_type,
                "error": last_run.error[:500] if last_run.error else "",
                "fetched_count": last_run.fetched_count,
                "new_count": last_run.new_count,
                "failed_count": last_run.failed_count,
                "started_at": iso_cn(last_run.started_at),
                "ended_at": iso_cn(last_run.ended_at),
            } if last_run else None,
        })
    return {"items": out}


@router.get("/insights/{insight_type}/posts")
def drill_posts(
    insight_type: str,
    community_id: int = Query(...),
    keyword: str = Query(""),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    import json

    from app.core.models import AnalysisResult

    stmt = select(Post, AnalysisResult).where(
        Post.community_id == community_id,
        Post.id == AnalysisResult.post_id,
    )
    if since is not None:
        stmt = stmt.where(Post.published_at >= since)
    if until is not None:
        stmt = stmt.where(Post.published_at <= until)

    rows = session.exec(stmt).all()
    items = []
    for post, result in rows:
        matched = False
        if insight_type == "topic":
            topics = json.loads(result.topics_json or "[]")
            matched = keyword in topics
        elif insight_type == "bug":
            bugs = json.loads(result.bugs_json or "[]")
            matched = any(b.get("summary") == keyword for b in bugs)
        elif insight_type == "suggestion":
            sugs = json.loads(result.suggestions_json or "[]")
            matched = any(s.get("summary") == keyword for s in sugs)
        elif insight_type == "review":
            reviews = json.loads(result.content_reviews_json or "[]")
            matched = any(r.get("subject") == keyword for r in reviews)

        if not matched:
            continue
        items.append({
            "id": post.id,
            "platform": post.platform,
            "taptap_post_id": post.taptap_post_id,
            "title": post.title,
            "author": post.author,
            "published_at": iso_cn(post.published_at),
            "sentiment": result.sentiment,
            "raw_url": post.raw_url,
        })
    return {"items": items}


# -------- 关键词管理 --------

@router.get("/keywords")
def get_keywords(category: Optional[str] = Query(None), session: Session = Depends(get_session)):
    return {"items": [k.dict() for k in list_keywords(session, category)]}


@router.post("/keywords")
def post_keyword(payload: KeywordCreate, session: Session = Depends(get_session)):
    kw = add_keyword(session, payload.word, payload.category)
    return kw.dict()


@router.delete("/keywords/{keyword_id}")
def remove_keyword(keyword_id: int, session: Session = Depends(get_session)):
    ok = delete_keyword(session, keyword_id)
    if not ok:
        raise HTTPException(status_code=404, detail="keyword not found")
    return {"deleted": True}


@router.patch("/keywords/{keyword_id}")
def patch_keyword(keyword_id: int, enabled: bool = Query(True), session: Session = Depends(get_session)):
    kw = toggle_keyword(session, keyword_id, enabled)
    if not kw:
        raise HTTPException(status_code=404, detail="keyword not found")
    return kw.dict()


# -------- 内容库 / 负面库 --------

@router.get("/content-library")
def get_content_library(
    community_id: Optional[int] = Query(None),
    platform: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    return {"items": content_library(session, community_id=community_id, platform=platform, keyword=keyword, sentiment=sentiment, since=since, until=until, limit=limit)}


@router.get("/negative-library")
def get_negative_library(
    community_id: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    return {"items": negative_library(session, community_id=community_id, limit=limit)}


# -------- 预警中心 --------

@router.get("/alerts")
def get_alerts(
    status: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"items": [a.dict() for a in list_alerts(session, status=status, level=level, limit=limit)]}


@router.post("/alerts/scan")
def scan_alerts(session: Session = Depends(get_session)):
    n = generate_alerts_for_negative(session)
    return {"generated": n}


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert_api(alert_id: int, session: Session = Depends(get_session)):
    a = resolve_alert(session, alert_id)
    if not a:
        raise HTTPException(status_code=404, detail="alert not found")
    return a.dict()


# -------- 简报 --------

class BriefingCreate(BaseModel):
    title: str
    period_start: datetime
    period_end: datetime
    summary: str = ""


@router.get("/briefings")
def get_briefings(limit: int = Query(50, ge=1, le=200), session: Session = Depends(get_session)):
    return {"items": [b.dict() for b in list_briefings(session, limit=limit)]}


@router.post("/briefings")
def post_briefing(payload: BriefingCreate, session: Session = Depends(get_session)):
    b = create_briefing(
        session,
        title=payload.title,
        period_start=payload.period_start,
        period_end=payload.period_end,
        summary=payload.summary,
    )
    return b.dict()


# -------- AI 分析评估 --------

class ReviewCreate(BaseModel):
    status: str = "correct"
    sentiment_correct: bool = True
    bugs_correct: bool = True
    suggestions_correct: bool = True
    topics_correct: bool = True
    content_reviews_correct: bool = True
    corrected_sentiment: str = ""
    corrected_bugs: list = []
    corrected_suggestions: list = []
    corrected_topics: list = []
    corrected_content_reviews: list = []


@router.get("/evaluation/posts")
def evaluation_posts(
    community_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return eval_list_posts(
        session,
        community_id=community_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("/evaluation/posts/{post_id}/review")
def evaluation_submit_review(
    post_id: int,
    payload: ReviewCreate,
    session: Session = Depends(get_session),
):
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="post not found")
    try:
        review = eval_submit_review(session, post_id, payload.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    from app.analyzer.evaluation import _review_to_dict
    return _review_to_dict(review)


@router.get("/evaluation/accuracy")
def evaluation_accuracy(
    community_id: Optional[int] = Query(None),
    session: Session = Depends(get_session),
):
    return eval_compute_accuracy(session, community_id=community_id)
