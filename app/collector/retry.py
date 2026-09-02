from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class MaxRetriesExceeded(RuntimeError):
    pass


def retry_with_backoff(
    func: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    factor: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    retriable: Callable[[Exception], bool] | None = None,
) -> T:
    """同步指数退避重试。max_retries 为额外重试次数（总尝试 = 1 + max_retries）。

    retriable(exc) 返回 False 的异常立即抛出，不重试。
    """
    last_exc: Exception | None = None
    total_attempts = max_retries + 1
    for attempt in range(total_attempts):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if retriable is not None and not retriable(exc):
                raise
            if attempt == total_attempts - 1:
                break
            delay = base_delay * (factor**attempt)
            sleep(delay)
    raise MaxRetriesExceeded(f"已超过最大重试次数 {max_retries}") from last_exc
