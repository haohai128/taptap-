from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.collector.rate_limit import RateLimiter
from app.collector.scheduler import CollectionScheduler
from app.collector.service import run_collection
from app.collector.taptap_adapter import TapTapWebApiAdapter
from app.analyzer.analyzer import SinglePostAnalyzer
from app.analyzer.client import build_openai_client
from app.analyzer.consumer import AnalysisConsumer
from app.core.config import AppConfig, load_config
from app.core.db import init_engine, create_all, get_engine
from app.core.models import Community
from app.dashboard.routes import router

logger = logging.getLogger(__name__)


_state: dict = {}


def _collect_community(community_id: int) -> None:
    """模块级采集函数（可被 APScheduler 序列化）。采集完成后立即分析新帖子。"""
    from sqlmodel import Session, select

    from app.analyzer.service import analyze_post, fetch_pending_posts
    from app.core.models import Post, PostStatus

    config: AppConfig = _state.get("config")
    engine = get_engine()
    from app.collector.registry import get_adapter
    with Session(engine) as session:
        community = session.get(Community, community_id)
        if not community:
            logger.warning("community %s not found", community_id)
            return
        if community.collect_status == "stopped":
            logger.info("community %s collect_status=stopped, skip scheduled collection", community_id)
            return
        adapter = get_adapter(community.platform)
        rl = _state.get("rate_limiter") or RateLimiter(
            min_interval_seconds=config.collector.min_request_interval_seconds if config else 2.0
        )
        run_collection(
            session,
            community,
            adapter,
            rl,
            max_retries=config.collector.max_retries if config else 3,
        )

    # 采集完成后立即分析该社区的待分析帖子（不等后台轮询）
    if not config or not config.ai:
        return
    try:
        analyzer = _analyzer_factory(config)()
        with Session(engine) as session:
            posts = session.exec(
                select(Post)
                .where(Post.community_id == community_id, Post.status == PostStatus.PENDING)
                .order_by(Post.id.asc())
                .limit(50)
            ).all()
            logger.info("post-collect analysis: %d pending posts for community %s", len(posts), community_id)
            for post in posts:
                analyze_post(session, post, analyzer, max_attempts=config.analyzer.max_attempts)
    except Exception as exc:
        logger.exception("post-collect analysis failed: %s", exc)


def _analyzer_factory(config: AppConfig):
    def _factory() -> SinglePostAnalyzer:
        client = build_openai_client(config.ai)
        return SinglePostAnalyzer(client, config.ai.model, use_json_mode=True)
    return _factory


def create_app(config: Optional[AppConfig] = None) -> FastAPI:
    if config is None:
        config = load_config(require_ai=True)

    init_engine(config)
    create_all()
    _state["config"] = config

    app = FastAPI(title="TapTap Community Sentiment", version="0.1.0")
    app.include_router(router, prefix="/api")

    rate_limiter = RateLimiter(min_interval_seconds=config.collector.min_request_interval_seconds)
    _state["rate_limiter"] = rate_limiter

    scheduler = CollectionScheduler(jobstore_url=config.database.url)
    scheduler.set_collect_function(_collect_community)
    scheduler.start()
    _state["scheduler"] = scheduler

    consumer = AnalysisConsumer(
        _analyzer_factory(config),
        batch_size=config.analyzer.batch_size,
        poll_interval_seconds=config.analyzer.poll_interval_seconds,
        max_attempts=config.analyzer.max_attempts,
    )
    consumer.start()
    _state["consumer"] = consumer

    static_dir = Path(__file__).parent / "static" / "dist"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def _spa_fallback(full_path: str):
            if full_path.startswith("api"):
                raise HTTPException(status_code=404, detail="not found")
            index = static_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            raise HTTPException(status_code=404, detail="not found")

    @app.on_event("shutdown")
    def _shutdown():
        scheduler.shutdown(wait=False)
        consumer.stop()

    return app


def schedule_community_after_register(community: Community) -> None:
    scheduler: Optional[CollectionScheduler] = _state.get("scheduler")
    if scheduler:
        scheduler.schedule_community(community.id, community.interval_seconds)


def unschedule_community_after_delete(community_id: int) -> None:
    scheduler: Optional[CollectionScheduler] = _state.get("scheduler")
    if scheduler:
        scheduler.unschedule_community(community_id)


def trigger_collect_now(community_id: int) -> None:
    scheduler: Optional[CollectionScheduler] = _state.get("scheduler")
    if scheduler:
        scheduler.trigger_now(community_id)


def run_server() -> None:
    import uvicorn

    config = load_config(require_ai=True)
    app = create_app(config)
    uvicorn.run(app, host=config.server.host, port=config.server.port)
