from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx


class CollectorErrorType(str, Enum):
    """统一风控/错误分类，所有平台 Adapter 共用。"""
    BLOCKED = "blocked"            # 403/412/验证码页面：平台主动拒绝
    RATE_LIMITED = "rate_limited"  # 429：频率限制
    AUTH_EXPIRED = "auth_expired"  # 401：登录失效
    NETWORK_ERROR = "network_error"  # 超时/连接错误
    HTTP_ERROR = "http_error"      # 其他非 2xx（5xx/4xx 非风控）


_BLOCKED_STATUS = {403, 412}
_RATE_LIMITED_STATUS = {429}
_AUTH_EXPIRED_STATUS = {401}
_CAPTCHA_MARKERS = ("验证码", "captcha", "请输入验证码", "访问受限", "安全验证", "风控", "risk control")


def classify_http_status(status_code: int) -> Optional[CollectorErrorType]:
    """按 HTTP 状态码判别风控类型，非风控返回 None。"""
    if status_code in _BLOCKED_STATUS:
        return CollectorErrorType.BLOCKED
    if status_code in _RATE_LIMITED_STATUS:
        return CollectorErrorType.RATE_LIMITED
    if status_code in _AUTH_EXPIRED_STATUS:
        return CollectorErrorType.AUTH_EXPIRED
    return None


@dataclass
class FetchedPost:
    taptap_post_id: str
    title: str
    content: str
    author: str
    published_at: Optional[datetime]
    reply_count: int
    like_count: int
    raw_url: str
    topic_id: str = ""
    is_elite: bool = False
    is_official: bool = False
    group_id: str = ""


class AntiCrawlError(RuntimeError):
    """检测到反爬拦截（验证码/封禁）时抛出。"""


class CommunityNotAccessibleError(RuntimeError):
    """社区链接无法解析或无法访问时抛出。"""


class CommunityAdapter(ABC):
    """社区抓取适配器抽象接口。新增数据源时实现该接口。

    合规声明：本适配器仅用于以正常请求方式获取公开数据，不绕过验证码、
    不破解风控、不伪造用户身份。平台明确拒绝请求时停止请求。
    """

    @abstractmethod
    def parse_community_id(self, raw_url: str) -> str:
        """将原始社区链接解析为稳定社区标识。解析失败抛 ValueError。"""

    @abstractmethod
    def fetch_post_list(self, community_id: str, limit: int) -> list[dict]:
        """抓取帖子列表（每项至少含 taptap_post_id 与 raw_url）。

        检测到反爬拦截时抛 AntiCrawlError；社区不可访问抛 CommunityNotAccessibleError。
        """

    @abstractmethod
    def fetch_post_detail(self, post_ref: dict) -> FetchedPost:
        """抓取单条帖子详情，返回 FetchedPost。"""

    @abstractmethod
    def is_anti_crawl_response(self, status_code: int, body_sample: str) -> bool:
        """根据状态码与响应体判断是否为反爬拦截。"""

    def classify_response(
        self,
        response: Optional[httpx.Response] = None,
        exception: Optional[Exception] = None,
    ) -> Optional[CollectorErrorType]:
        """统一风控信号识别。子类可覆写以补充平台特定特征，但分类体系统一。

        - 网络超时/连接异常 → network_error
        - 状态码 403/412 → blocked
        - 状态码 429 → rate_limited
        - 状态码 401 → auth_expired
        - 200 但响应体匹配验证码/风控关键词 → blocked
        - 其他非 2xx → http_error（非风控）
        - 2xx / 无异常 → None
        """
        if exception is not None:
            if isinstance(exception, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, ConnectionError)):
                return CollectorErrorType.NETWORK_ERROR
            return None

        if response is None:
            return None

        status = response.status_code
        mapped = classify_http_status(status)
        if mapped is not None:
            return mapped

        if 200 <= status < 300:
            body = ""
            try:
                body = response.text[:2000].lower()
            except Exception:
                body = ""
            if any(marker.lower() in body for marker in _CAPTCHA_MARKERS):
                return CollectorErrorType.BLOCKED
            return None

        if status >= 400:
            return CollectorErrorType.HTTP_ERROR

        return None
