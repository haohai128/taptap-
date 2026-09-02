from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from openai import OpenAI

from app.analyzer.parser import (
    AnalysisParseError,
    AnalysisPayload,
    parse_analysis_json,
    payload_to_db_json,
)
from app.analyzer.prompts import SYSTEM_PROMPT, build_user_prompt


class AnalysisError(RuntimeError):
    pass


class SinglePostAnalyzer:
    """单帖分析器：调用兼容 OpenAI API，解析并返回结构化结果。

    支持 response_format=json 的端点优先用之；不支持时退化到 prompt + 解析重试。
    """

    def __init__(
        self,
        client: OpenAI,
        model: str,
        *,
        use_json_mode: bool = True,
        parse_retries: int = 2,
    ):
        self._client = client
        self._model = model
        self._use_json_mode = use_json_mode
        self._parse_retries = parse_retries

    def analyze(self, title: str, content: str) -> AnalysisPayload:
        user_prompt = build_user_prompt(title, content)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if self._use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_exc: Exception | None = None
        attempts = self._parse_retries + 1
        for attempt in range(attempts):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                raw = resp.choices[0].message.content or ""
                return parse_analysis_json(raw)
            except AnalysisParseError as exc:
                last_exc = exc
                if attempt < attempts - 1 and self._use_json_mode:
                    kwargs["messages"].append(
                        {"role": "assistant", "content": raw}
                    )
                    kwargs["messages"].append(
                        {
                            "role": "user",
                            "content": "上一次输出不是合法 JSON。请仅输出符合 schema 的 JSON。",
                        }
                    )
                    continue
                raise AnalysisError(f"解析失败: {exc}") from exc
            except Exception as exc:
                raise AnalysisError(f"调用 AI API 失败: {exc}") from exc

        raise AnalysisError(f"解析失败: {last_exc}")
