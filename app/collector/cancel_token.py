"""社区级采集取消令牌（进程内内存态）。

提供协作式取消：stop-collection API 设置令牌后，正在执行的 run_collection
在每次翻页/每帖详情前检查令牌，被设置则跳出循环并以 STOPPED 状态收尾。

单进程部署下足够；多进程场景需改为 DB 标志轮询（见 design.md Open Questions）。
"""
from __future__ import annotations

from threading import Event, Lock
from typing import Dict


_tokens: Dict[int, Event] = {}
_lock = Lock()


def _get_or_create(community_id: int) -> Event:
    with _lock:
        if community_id not in _tokens:
            _tokens[community_id] = Event()
        return _tokens[community_id]


def request_stop(community_id: int) -> None:
    """请求停止指定社区的采集。幂等。"""
    _get_or_create(community_id).set()


def clear_stop(community_id: int) -> None:
    """清除停止令牌（重新启用采集）。幂等。"""
    with _lock:
        ev = _tokens.pop(community_id, None)
    if ev is not None:
        ev.clear()


def is_stop_requested(community_id: int) -> bool:
    """返回该社区是否被请求停止。"""
    with _lock:
        ev = _tokens.get(community_id)
    return ev is not None and ev.is_set()
