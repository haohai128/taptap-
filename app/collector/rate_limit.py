from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """按域名最小请求间隔限速器（线程安全，亦兼容 asyncio.sleep）。"""

    def __init__(self, min_interval_seconds: float = 2.0):
        self._min_interval = max(0.0, float(min_interval_seconds))
        self._last: dict[str, float] = defaultdict(lambda: 0.0)
        self._lock = Lock()

    def _domain(self, url: str) -> str:
        from urllib.parse import urlparse

        return urlparse(url).netloc.lower() or "global"

    def next_allowed(self, url: str, now: float | None = None) -> float:
        domain = self._domain(url)
        now = time.monotonic() if now is None else now
        with self._lock:
            last = self._last[domain]
            wait = max(0.0, last + self._min_interval - now)
            scheduled = now + wait
            self._last[domain] = scheduled
            return wait

    async def async_wait(self, url: str) -> None:
        wait = self.next_allowed(url)
        if wait > 0:
            await asyncio.sleep(wait)

    def sync_wait(self, url: str) -> None:
        wait = self.next_allowed(url)
        if wait > 0:
            time.sleep(wait)
