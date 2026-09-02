from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.models import AnalysisResult, Post, Review, ReviewStatus
from app.core.tz import now_cn, iso_cn


REVIEW_DIMENSIONS = (
    "sentiment",
    "bugs",
    "suggestions",
    "topics",
    "content_reviews",
)


@dataclass
class EvaluationPostItem:
    post: dict[str, Any]
    analysis: Optional[dict[str, Any]]
    review: Optional[dict[str, Any]]


def _post_to_dict(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "community_id": post.community_id,
        "taptap_post_id": post.taptap_post_id,
        "platform": post.platform,
        "title": post.title,
        "content": post.content,
        "author": post.author,
        "published_at": iso_cn(post.published_at),
        "reply_count": post.reply_count,
        "like_count": post.like_count,
        "raw_url": post.raw_url,
        "status": post.status.value if hasattr(post.status, "value") else post.status,
        "topic_id": post.topic_id,
        "is_elite": post.is_elite,
        "is_official": post.is_official,
        "group_id": post.group_id,
        "fetched_at": iso_cn(post.fetched_at),
    }


def _analysis_to_dict(ar: AnalysisResult) -> dict[str, Any]:
    def _loads(s: str, default: Any):
        try:
            return json.loads(s) if s else default
        except (TypeError, ValueError):
            return default

    return {
        "id": ar.id,
        "post_id": ar.post_id,
        "topics": _loads(ar.topics_json, []),
        "sentiment": ar.sentiment,
        "sentiment_reason": ar.sentiment_reason,
        "bugs": _loads(ar.bugs_json, []),
        "suggestions": _loads(ar.suggestions_json, []),
        "content_reviews": _loads(ar.content_reviews_json, []),
        "analyzed_at": iso_cn(ar.analyzed_at),
    }


def _review_to_dict(r: Review) -> dict[str, Any]:
    def _loads(s: str, default: Any):
        try:
            return json.loads(s) if s else default
        except (TypeError, ValueError):
            return default

    return {
        "id": r.id,
        "post_id": r.post_id,
        "analysis_result_id": r.analysis_result_id,
        "status": r.status,
        "sentiment_correct": r.sentiment_correct,
        "bugs_correct": r.bugs_correct,
        "suggestions_correct": r.suggestions_correct,
        "topics_correct": r.topics_correct,
        "content_reviews_correct": r.content_reviews_correct,
        "corrected_sentiment": r.corrected_sentiment,
        "corrected_bugs": _loads(r.corrected_bugs_json, []),
        "corrected_suggestions": _loads(r.corrected_suggestions_json, []),
        "corrected_topics": _loads(r.corrected_topics_json, []),
        "corrected_content_reviews": _loads(r.corrected_content_reviews_json, []),
        "reviewed_at": iso_cn(r.reviewed_at),
    }


def list_evaluation_posts(
    session: Session,
    community_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """联合查询 Post + AnalysisResult + Review，按审核状态筛选并分页。

    status:
      - unreviewed: 仅有 AnalysisResult、无 Review
      - reviewed:   有 Review
      - incorrect:  Review.status in (incorrect, partial)
      - None:       全部
    """
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))

    stmt = (
        select(Post, AnalysisResult, Review)
        .join(AnalysisResult, AnalysisResult.post_id == Post.id)
        .outerjoin(Review, Review.post_id == Post.id)
        .where(Post.status == "analyzed")
    )
    if community_id is not None:
        stmt = stmt.where(Post.community_id == community_id)

    if status == "unreviewed":
        stmt = stmt.where(Review.id.is_(None))
    elif status == "reviewed":
        stmt = stmt.where(Review.id.is_not(None))
    elif status == "incorrect":
        stmt = stmt.where(Review.status.in_([ReviewStatus.INCORRECT.value, ReviewStatus.PARTIAL.value]))

    stmt = stmt.order_by(Post.published_at.desc().nullslast() if False else Post.id.desc())

    rows = list(session.exec(stmt).all())
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]

    items = []
    for post, ar, review in page_rows:
        items.append({
            "post": _post_to_dict(post),
            "analysis": _analysis_to_dict(ar),
            "review": _review_to_dict(review) if review else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def submit_review(
    session: Session,
    post_id: int,
    payload: dict[str, Any],
) -> Review:
    """upsert Review（post_id 存在则更新）。返回保存后的 Review。"""
    status = str(payload.get("status", ReviewStatus.CORRECT.value))
    if status not in {s.value for s in ReviewStatus}:
        raise ValueError(f"非法 status: {status}")

    ar = session.exec(select(AnalysisResult).where(AnalysisResult.post_id == post_id)).first()
    analysis_result_id = ar.id if ar else None

    existing = session.exec(select(Review).where(Review.post_id == post_id)).first()
    if existing is None:
        existing = Review(post_id=post_id, analysis_result_id=analysis_result_id)
    else:
        existing.analysis_result_id = analysis_result_id or existing.analysis_result_id

    existing.status = status
    existing.sentiment_correct = bool(payload.get("sentiment_correct", True))
    existing.bugs_correct = bool(payload.get("bugs_correct", True))
    existing.suggestions_correct = bool(payload.get("suggestions_correct", True))
    existing.topics_correct = bool(payload.get("topics_correct", True))
    existing.content_reviews_correct = bool(payload.get("content_reviews_correct", True))

    existing.corrected_sentiment = str(payload.get("corrected_sentiment", "") or "")
    existing.corrected_bugs_json = _dumps(payload.get("corrected_bugs", []))
    existing.corrected_suggestions_json = _dumps(payload.get("corrected_suggestions", []))
    existing.corrected_topics_json = _dumps(payload.get("corrected_topics", []))
    existing.corrected_content_reviews_json = _dumps(payload.get("corrected_content_reviews", []))
    existing.reviewed_at = now_cn()

    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def _dumps(value: Any) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def compute_accuracy(session: Session, community_id: Optional[int] = None) -> dict[str, Any]:
    """计算各维度准确率与总体准确率。

    无 Review 时返回全 0 不报错。
    """
    stmt = (
        select(Review)
        .join(Post, Post.id == Review.post_id)
        .where(Post.status == "analyzed")
    )
    if community_id is not None:
        stmt = stmt.where(Post.community_id == community_id)

    reviews = list(session.exec(stmt).all())
    total = len(reviews)

    def _rate(field: str) -> float:
        if total == 0:
            return 0.0
        ok = sum(1 for r in reviews if getattr(r, field))
        return round(ok / total * 100, 2)

    sentiment_rate = _rate("sentiment_correct")
    bugs_rate = _rate("bugs_correct")
    suggestions_rate = _rate("suggestions_correct")
    topics_rate = _rate("topics_correct")
    content_reviews_rate = _rate("content_reviews_correct")

    if total == 0:
        overall = 0.0
    else:
        per_post_correct = sum(
            1
            for r in reviews
            if r.sentiment_correct
            and r.bugs_correct
            and r.suggestions_correct
            and r.topics_correct
            and r.content_reviews_correct
        )
        overall = round(per_post_correct / total * 100, 2)

    correct_count = sum(1 for r in reviews if r.status == ReviewStatus.CORRECT.value)
    incorrect_count = sum(1 for r in reviews if r.status == ReviewStatus.INCORRECT.value)
    partial_count = sum(1 for r in reviews if r.status == ReviewStatus.PARTIAL.value)

    return {
        "total": total,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "partial_count": partial_count,
        "sentiment_accuracy": sentiment_rate,
        "bugs_accuracy": bugs_rate,
        "suggestions_accuracy": suggestions_rate,
        "topics_accuracy": topics_rate,
        "content_reviews_accuracy": content_reviews_rate,
        "overall_accuracy": overall,
    }
