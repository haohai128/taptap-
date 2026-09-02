from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from app.core.config import AIConfig


class AIClientNotConfigured(RuntimeError):
    pass


def build_openai_client(config: AIConfig) -> OpenAI:
    """从 AIConfig 构建 OpenAI 兼容客户端。"""
    if not config or not config.base_url or not config.model:
        raise AIClientNotConfigured(
            "缺少 AI 配置：需要 OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL"
        )
    return OpenAI(
        base_url=config.base_url,
        api_key=config.api_key or "unused",
        timeout=180.0,
        max_retries=2,
    )


def build_client_from_env() -> tuple[OpenAI, str]:
    """便捷工厂：直接从环境变量构建并返回 (client, model)。"""
    from app.core.config import _build_ai

    ai = _build_ai()
    return build_openai_client(ai), ai.model
