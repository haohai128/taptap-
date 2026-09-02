from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.collector.adapter import (
    AntiCrawlError,
    CommunityAdapter,
    CommunityNotAccessibleError,
    FetchedPost,
)


_TAPTAP_APP_PATTERN = re.compile(r"/app/(\d+)")
_ANTI_CRAWL_MARKERS = ("验证码", "captcha", "请输入验证码", "访问受限", "blocked")
_DEFAULT_XUA_TEMPLATE = (
    "V%3D1%26PN%3DWebApp%26LANG%3Dzh_CN%26VN_CODE%3D102%26VN%3D0.1.0"
    "%26LOC%3DCN%26PLT%3DPC%26DS%3DAndroid%26UID%3D{uid}%26DT%3DPC%26OS%3DWindows"
)


def _make_xua(uid: Optional[str] = None) -> str:
    return _DEFAULT_XUA_TEMPLATE.format(uid=uid or str(uuid.uuid4()))


class TapTapWebApiAdapter(CommunityAdapter):
    """基于 TapTap 官方 webapi 的通用社区论坛（Topic）采集适配器。

    采集流程：
    1. `fetch_post_list` 首先确保 group_id 已知（传入或自动发现）。
    2. 自动发现：调用 `feed/v7/for-app-detail?app_id={app_id}`，从任意 moment 的
       `group.id` 提取 group_id。
    3. 拉取帖子：循环调用 `feed/v7/by-group?group_id={gid}&from={offset}&limit={n}`
       分页获取论坛 Topic 帖子（不传 sort，该参数会触发 400）。
    4. `fetch_post_detail` 从 moment 结构解析 topic.title / topic.summary 等字段。

    适配器不硬编码任何 app_id 或 group_id，任意 TapTap 社区均可复用。
    """

    BASE = "https://www.taptap.cn"

    def __init__(self, client: httpx.Client):
        self._client = client
        self._xua = _make_xua()

    def parse_community_id(self, raw_url: str) -> str:
        parsed = urlparse(raw_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"无效的 TapTap 社区链接: {raw_url}")
        m = _TAPTAP_APP_PATTERN.search(parsed.path)
        if m:
            return f"app:{m.group(1)}"
        if parsed.path.strip("/"):
            slug = parsed.path.strip("/").split("/")[0]
            if slug:
                return f"slug:{slug}"
        raise ValueError(f"无法从链接解析社区标识: {raw_url}")

    def is_anti_crawl_response(self, status_code: int, body_sample: str) -> bool:
        if status_code in (403, 429):
            return True
        if status_code == 400 and "INVALID_XUA" in body_sample:
            return False
        sample = body_sample[:2000].lower()
        return any(marker.lower() in sample for marker in _ANTI_CRAWL_MARKERS)

    def fetch_post_list(
        self,
        community_id: str,
        limit: int,
        *,
        group_id: Optional[str] = None,
    ) -> list[dict]:
        """抓取 Topic 帖子列表。

        Args:
            community_id: 形如 "app:139029" 的社区标识。
            limit: 本次采集的帖子上限。
            group_id: 可选的已缓存 group_id；为 None 时自动发现。

        Returns:
            list[dict]，每项含 taptap_post_id、raw_url、_moment、_item、group_id。
        """
        app_id = self._extract_app_id(community_id)

        if not group_id:
            group_id = self._discover_group_id(app_id)
            if not group_id:
                raise CommunityNotAccessibleError(
                    f"group_id 发现失败: 无法从 for-app-detail 获取社区 {community_id} 的论坛 group_id"
                )

        out: list[dict] = []
        offset = 0
        page_size = min(limit, 10) if limit > 0 else 10
        while len(out) < limit:
            page = self._fetch_by_group_page(group_id, offset, page_size)
            if not page:
                break
            for it in page:
                m = it.get("moment", {}) or {}
                mid = m.get("id_str") or str(m.get("id", ""))
                if not mid:
                    continue
                out.append({
                    "taptap_post_id": mid,
                    "raw_url": f"{self.BASE}/moment/{mid}",
                    "_moment": m,
                    "_item": it,
                    "group_id": group_id,
                })
                if len(out) >= limit:
                    break
            if len(page) < page_size:
                break
            offset += page_size
        return out

    def fetch_post_detail(self, post_ref: dict) -> FetchedPost:
        m = post_ref.get("_moment") or {}
        topic = m.get("topic") or {}
        author_info = (m.get("author") or {}).get("user") or {}
        stat = m.get("stat") or {}
        group = m.get("group") or {}

        title = (topic.get("title") or "").strip() or "(无标题)"
        content = (topic.get("summary") or "").strip()
        published_at = self._ts_to_dt(m.get("publish_time") or m.get("created_time"))

        return FetchedPost(
            taptap_post_id=post_ref["taptap_post_id"],
            title=title,
            content=content,
            author=author_info.get("name", "") or "",
            published_at=published_at,
            reply_count=int(stat.get("feedback_status", 0) or 0),
            like_count=int(stat.get("ups", 0) or 0),
            raw_url=post_ref["raw_url"],
            topic_id=str(topic.get("id_str") or topic.get("id") or ""),
            is_elite=bool(m.get("is_elite") or False),
            is_official=bool(m.get("is_official") or False),
            group_id=str(group.get("id") or post_ref.get("group_id") or ""),
        )

    def _discover_group_id(self, app_id: str) -> Optional[str]:
        """调用 for-app-detail，从返回的 moment.group.id 提取 group_id。"""
        url = (
            f"{self.BASE}/webapiv2/feed/v7/for-app-detail"
            f"?app_id={app_id}&limit=10&X-UA={self._xua}"
        )
        resp = self._get_json(url)
        if resp.status_code == 404:
            return None
        if self.is_anti_crawl_response(resp.status_code, resp.text):
            raise AntiCrawlError(f"反爬拦截: status={resp.status_code}")
        try:
            data = resp.json()
        except Exception:
            return None
        if not data.get("success", False):
            msg = data.get("data", {}).get("msg", "")
            if "INVALID_XUA" in str(msg):
                self._xua = _make_xua()
                return self._discover_group_id(app_id)
            return None
        items = data.get("data", {}).get("list", []) or []
        for it in items:
            m = it.get("moment", {}) or {}
            g = m.get("group") or {}
            gid = g.get("id")
            if gid:
                return str(gid)
        return None

    def _fetch_by_group_page(self, group_id: str, offset: int, page_size: int) -> list[dict]:
        url = (
            f"{self.BASE}/webapiv2/feed/v7/by-group"
            f"?group_id={group_id}&from={offset}&limit={page_size}&X-UA={self._xua}"
        )
        resp = self._get_json(url)
        if resp.status_code == 404:
            return []
        if self.is_anti_crawl_response(resp.status_code, resp.text):
            raise AntiCrawlError(f"反爬拦截: status={resp.status_code}")
        try:
            data = resp.json()
        except Exception:
            return []
        if not data.get("success", False):
            return []
        return data.get("data", {}).get("list", []) or []

    def _extract_app_id(self, community_id: str) -> str:
        if community_id.startswith("app:"):
            return community_id.split(":", 1)[1]
        if community_id.startswith("slug:"):
            raise CommunityNotAccessibleError("slug 形式暂不支持，请使用 /app/<id> 链接")
        return community_id

    def _get_json(self, url: str) -> httpx.Response:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.BASE}/app/",
        }
        return self._client.get(url, headers=headers, follow_redirects=True, timeout=20.0)

    @staticmethod
    def _ts_to_dt(ts) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone(timedelta(hours=8)))
        except (TypeError, ValueError, OSError):
            return None


TapTapAdapter = TapTapWebApiAdapter
