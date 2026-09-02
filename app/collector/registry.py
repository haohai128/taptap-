"""采集适配器注册表。当前仅支持 TapTap 平台。"""
from __future__ import annotations

from app.collector.adapter import CommunityAdapter
from app.collector.taptap_adapter import TapTapWebApiAdapter
from app.core.models import Platform
import httpx


def get_adapter(platform: str, client: httpx.Client | None = None) -> CommunityAdapter:
    """返回 TapTap 采集适配器实例。"""
    cli = client or httpx.Client()
    return TapTapWebApiAdapter(cli)


def supported_platforms() -> list[dict]:
    return [
        {"value": Platform.TAPTAP.value, "label": "TapTap", "implemented": True},
    ]
