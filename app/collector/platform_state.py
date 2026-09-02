"""平台采集状态聚合（内存态）。

每个平台独立持有状态，单平台风控不波及其他平台。
系统重启后状态恢复为"正常"，由下次采集重新驱动。
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from app.core.tz import now_cn, iso_cn


# 平台状态枚举值
STATUS_NORMAL = "normal"
STATUS_COLLECTING = "collecting"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_BLOCKED = "blocked"
STATUS_AUTH_EXPIRED = "auth_expired"
STATUS_NETWORK_ERROR = "network_error"


_state: dict[str, dict] = {}
_lock = Lock()


def update_platform_state(
    platform: str,
    status: str,
    *,
    error: Optional[str] = None,
    last_run_at: Optional[datetime] = None,
) -> None:
    """更新某平台当前状态。单平台更新不影响其他平台。"""
    with _lock:
        _state[platform] = {
            "platform": platform,
            "status": status,
            "error": error or "",
            "last_run_at": iso_cn(last_run_at or now_cn()),
        }


def get_platform_states() -> dict[str, dict]:
    """返回所有平台当前状态。"""
    with _lock:
        return {k: dict(v) for k, v in _state.items()}


def get_platform_state(platform: str) -> Optional[dict]:
    with _lock:
        return dict(_state[platform]) if platform in _state else None


def reset_platform_state(platform: Optional[str] = None) -> None:
    """重置状态。platform=None 重置全部（用于测试/重启）。"""
    with _lock:
        if platform is None:
            _state.clear()
        else:
            _state.pop(platform, None)
