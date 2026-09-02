from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

VALID_SENTIMENTS = {"positive", "negative", "neutral", "unknown"}


@dataclass
class BugItem:
    summary: str = ""
    impact: str = ""


@dataclass
class SuggestionItem:
    summary: str = ""
    category: str = ""


@dataclass
class ContentReviewItem:
    subject: str = ""
    sentiment: str = "neutral"
    summary: str = ""


@dataclass
class AnalysisPayload:
    topics: list[str] = field(default_factory=list)
    sentiment: str = "unknown"
    sentiment_reason: str = ""
    bugs: list[BugItem] = field(default_factory=list)
    suggestions: list[SuggestionItem] = field(default_factory=list)
    content_reviews: list[ContentReviewItem] = field(default_factory=list)


class AnalysisParseError(ValueError):
    pass


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_analysis_json(raw: str) -> AnalysisPayload:
    """解析 AI 返回的 JSON 文本为 AnalysisPayload，严格校验五类字段。"""
    if not raw or not raw.strip():
        raise AnalysisParseError("空响应")

    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AnalysisParseError(f"JSON 解析失败: {exc}") from exc

    if not isinstance(data, dict):
        raise AnalysisParseError("顶层不是对象")

    topics_raw = data.get("topics", [])
    if not isinstance(topics_raw, list):
        raise AnalysisParseError("topics 不是数组")
    topics = [_as_str(t) for t in topics_raw if _as_str(t)]

    sentiment = _as_str(data.get("sentiment"), "unknown").lower()
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "unknown"

    sentiment_reason = _as_str(data.get("sentiment_reason"))

    bugs: list[BugItem] = []
    for b in data.get("bugs", []) or []:
        if not isinstance(b, dict):
            continue
        bugs.append(BugItem(summary=_as_str(b.get("summary")), impact=_as_str(b.get("impact"))))

    suggestions: list[SuggestionItem] = []
    for s in data.get("suggestions", []) or []:
        if not isinstance(s, dict):
            continue
        suggestions.append(
            SuggestionItem(summary=_as_str(s.get("summary")), category=_as_str(s.get("category")))
        )

    content_reviews: list[ContentReviewItem] = []
    for c in data.get("content_reviews", []) or []:
        if not isinstance(c, dict):
            continue
        c_sent = _as_str(c.get("sentiment"), "neutral").lower()
        if c_sent not in {"positive", "negative", "neutral"}:
            c_sent = "neutral"
        content_reviews.append(
            ContentReviewItem(
                subject=_as_str(c.get("subject")),
                sentiment=c_sent,
                summary=_as_str(c.get("summary")),
            )
        )

    return AnalysisPayload(
        topics=topics,
        sentiment=sentiment,
        sentiment_reason=sentiment_reason,
        bugs=bugs,
        suggestions=suggestions,
        content_reviews=content_reviews,
    )


def payload_to_db_json(payload: AnalysisPayload) -> dict[str, str]:
    """将 payload 各数组序列化为落库用的 JSON 字符串。"""
    return {
        "topics_json": json.dumps(payload.topics, ensure_ascii=False),
        "sentiment": payload.sentiment,
        "sentiment_reason": payload.sentiment_reason,
        "bugs_json": json.dumps(
            [{"summary": b.summary, "impact": b.impact} for b in payload.bugs],
            ensure_ascii=False,
        ),
        "suggestions_json": json.dumps(
            [{"summary": s.summary, "category": s.category} for s in payload.suggestions],
            ensure_ascii=False,
        ),
        "content_reviews_json": json.dumps(
            [
                {"subject": c.subject, "sentiment": c.sentiment, "summary": c.summary}
                for c in payload.content_reviews
            ],
            ensure_ascii=False,
        ),
    }
