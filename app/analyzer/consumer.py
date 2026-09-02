from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable, Optional

from sqlmodel import Session

from app.analyzer.analyzer import SinglePostAnalyzer
from app.analyzer.service import analyze_post, fetch_pending_posts
from app.core.db import get_engine

logger = logging.getLogger(__name__)


class AnalysisConsumer:
    """后台分析消费者：周期扫描待分析帖子并按批送入 AI。"""

    def __init__(
        self,
        analyzer_factory: Callable[[], SinglePostAnalyzer],
        *,
        batch_size: int = 20,
        poll_interval_seconds: int = 30,
        max_attempts: int = 3,
    ):
        self._factory = analyzer_factory
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._max_attempts = max_attempts
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="analysis-consumer")
        self._thread.start()
        logger.info("AnalysisConsumer started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("AnalysisConsumer stopped")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.exception("analysis tick failed: %s", exc)
            self._stop_event.wait(self._poll_interval)

    def _tick(self) -> None:
        engine = get_engine()
        analyzer = self._factory()
        with Session(engine) as session:
            posts = fetch_pending_posts(session, community_id=None, batch_size=self._batch_size)
            if not posts:
                return
            for post in posts:
                if self._stop_event.is_set():
                    break
                analyze_post(session, post, analyzer, max_attempts=self._max_attempts)
