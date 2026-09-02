from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Optional

from app.collector.adapter import CollectorErrorType


class PlatformRateLimiter:
    """平台级限速与指数退避器。

    每个 platform key 独立持有：
    - last_request_at：上次请求时间
    - backoff_until：退避结束时间
    - consecutive_errors：连续错误数

    平台 A 退避不占用平台 B 配额。线程安全。
    """

    def __init__(
        self,
        default_min_interval: float = 2.0,
        default_max_retries: int = 3,
        default_backoff_factor: float = 2.0,
        default_backoff_cap: float = 60.0,
    ):
        self._default_min_interval = default_min_interval
        self._default_max_retries = default_max_retries
        self._default_backoff_factor = default_backoff_factor
        self._default_backoff_cap = default_backoff_cap
        self._lock = threading.Lock()
        self._last_request: dict[str, float] = defaultdict(lambda: 0.0)
        self._backoff_until: dict[str, float] = defaultdict(lambda: 0.0)
        self._consecutive_errors: dict[str, int] = defaultdict(lambda: 0)

    def wait(self, platform: str, min_interval: Optional[float] = None) -> None:
        """阻塞等待直到允许下一次请求（兼顾最小间隔与退避）。"""
        interval = min_interval if min_interval is not None else self._default_min_interval
        now = time.monotonic()
        with self._lock:
            backoff_until = self._backoff_until[platform]
            last = self._last_request[platform]
            wait_until = max(last + interval, backoff_until, now)
            sleep_seconds = max(0.0, wait_until - now)
            self._last_request[platform] = wait_until
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def record_success(self, platform: str) -> None:
        with self._lock:
            self._consecutive_errors[platform] = 0
            self._backoff_until[platform] = 0.0

    def record_failure(
        self,
        platform: str,
        error_type: Optional[CollectorErrorType] = None,
        *,
        backoff_factor: Optional[float] = None,
        backoff_cap: Optional[float] = None,
    ) -> float:
        """记录失败并计算退避。返回建议的退避秒数（已写入 backoff_until）。

        blocked / auth_expired：直接退避到上限（本次采集将停止，退避值仅供后续判断）
        rate_limited / network_error / http_error：指数退避
        """
        factor = backoff_factor if backoff_factor is not None else self._default_backoff_factor
        cap = backoff_cap if backoff_cap is not None else self._default_backoff_cap
        with self._lock:
            self._consecutive_errors[platform] += 1
            n = self._consecutive_errors[platform]

            if error_type in (CollectorErrorType.BLOCKED, CollectorErrorType.AUTH_EXPIRED):
                delay = cap
            else:
                delay = min(cap, (factor ** n))

            backoff_until = time.monotonic() + delay
            self._backoff_until[platform] = backoff_until
            return delay

    def get_state(self, platform: str) -> dict:
        with self._lock:
            now = time.monotonic()
            backoff_until = self._backoff_until[platform]
            return {
                "platform": platform,
                "consecutive_errors": self._consecutive_errors[platform],
                "backoff_remaining": max(0.0, backoff_until - now),
                "in_backoff": backoff_until > now,
            }

    def is_in_backoff(self, platform: str) -> bool:
        with self._lock:
            return self._backoff_until[platform] > time.monotonic()
