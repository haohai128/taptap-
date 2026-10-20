from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.models import Alert, AlertLevel, AlertStatus, Briefing, Keyword, KeywordCategory, Post, AnalysisResult, Community
from app.core.tz import now_cn, iso_cn


def _loads(s: str | None, default: Any = None) -> Any:
    if not s:
        return default if default is not None else []
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default if default is not None else []


def list_keywords(session: Session, category: Optional[str] = None) -> list[Keyword]:
    stmt = select(Keyword)
    if category:
        stmt = stmt.where(Keyword.category == category)
    return list(session.exec(stmt).all())


def add_keyword(session: Session, word: str, category: str = KeywordCategory.NEGATIVE.value) -> Keyword:
    word = word.strip()
    existing = session.exec(
        select(Keyword).where(Keyword.word == word, Keyword.category == category)
    ).first()
    if existing:
        return existing
    kw = Keyword(word=word, category=category, enabled=True)
    session.add(kw)
    session.commit()
    session.refresh(kw)
    return kw


def delete_keyword(session: Session, keyword_id: int) -> bool:
    kw = session.get(Keyword, keyword_id)
    if not kw:
        return False
    session.delete(kw)
    session.commit()
    return True


def toggle_keyword(session: Session, keyword_id: int, enabled: bool) -> Optional[Keyword]:
    kw = session.get(Keyword, keyword_id)
    if not kw:
        return None
    kw.enabled = enabled
    session.add(kw)
    session.commit()
    session.refresh(kw)
    return kw


def create_alert(
    session: Session,
    *,
    post_id: Optional[int],
    community_id: Optional[int],
    level: str,
    title: str,
    detail: str,
    keyword: str = "",
) -> Alert:
    alert = Alert(
        post_id=post_id,
        community_id=community_id,
        level=level,
        status=AlertStatus.OPEN.value,
        title=title,
        detail=detail,
        keyword=keyword,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


def list_alerts(
    session: Session,
    *,
    status: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100,
) -> list[Alert]:
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if status:
        stmt = stmt.where(Alert.status == status)
    if level:
        stmt = stmt.where(Alert.level == level)
    return list(session.exec(stmt.limit(limit)).all())


def resolve_alert(session: Session, alert_id: int) -> Optional[Alert]:
    alert = session.get(Alert, alert_id)
    if not alert:
        return None
    alert.status = AlertStatus.RESOLVED.value
    alert.resolved_at = now_cn()
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


def generate_alerts_for_negative(session: Session) -> int:
    """扫描负面库关键词，对命中且情绪为负面的帖子生成预警。返回新增预警数。"""
    negative_words = list_keywords(session, KeywordCategory.NEGATIVE.value)
    negative_words = [k for k in negative_words if k.enabled]
    if not negative_words:
        return 0

    count = 0
    for kw in negative_words:
        stmt = select(Post, AnalysisResult).where(
            Post.id == AnalysisResult.post_id,
            Post.content.contains(kw.word),
            AnalysisResult.sentiment == "negative",
        )
        rows = session.exec(stmt).all()
        for post, _ in rows:
            exists = session.exec(
                select(Alert).where(
                    Alert.post_id == post.id,
                    Alert.keyword == kw.word,
                )
            ).first()
            if exists:
                continue
            create_alert(
                session,
                post_id=post.id,
                community_id=post.community_id,
                level=AlertLevel.CRITICAL.value,
                title=f"负面舆情命中: {kw.word}",
                detail=post.title[:200],
                keyword=kw.word,
            )
            count += 1
    return count


def create_briefing(
    session: Session,
    *,
    title: str,
    period_start: datetime,
    period_end: datetime,
    summary: str,
    stats_json: str = "{}",
) -> Briefing:
    b = Briefing(
        title=title,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        stats_json=stats_json,
    )
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def list_briefings(session: Session, limit: int = 50) -> list[Briefing]:
    return list(
        session.exec(
            select(Briefing).order_by(Briefing.created_at.desc()).limit(limit)
        ).all()
    )


def content_library(
    session: Session,
    *,
    community_id: Optional[int] = None,
    platform: Optional[str] = None,
    keyword: Optional[str] = None,
    sentiment: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 200,
) -> list[dict]:
    """内容库：可按多维度筛选的帖子+分析结果联合视图。

    使用左连接，未分析的帖子也会展示（sentiment 为 None），
    便于采集后立即可见。
    """
    stmt = select(Post, AnalysisResult, Community).outerjoin(
        AnalysisResult, Post.id == AnalysisResult.post_id
    ).join(Community, Community.id == Post.community_id)
    if community_id:
        stmt = stmt.where(Post.community_id == community_id)
    if platform:
        stmt = stmt.where(Post.platform == platform)
    if sentiment:
        stmt = stmt.where(AnalysisResult.sentiment == sentiment)
    if since:
        stmt = stmt.where(Post.published_at >= since)
    if until:
        stmt = stmt.where(Post.published_at <= until)
    stmt = stmt.order_by(Post.published_at.desc()).limit(limit)
    rows = session.exec(stmt).all()

    items = []
    for p, r, c in rows:
        if keyword and keyword not in ((p.title or "") + (p.content or "")):
            continue
        items.append({
            "id": p.id,
            "community_id": p.community_id,
            "community_name": c.name if c else "",
            "platform": p.platform,
            "title": p.title,
            "content": p.content,
            "author": p.author,
            "published_at": iso_cn(p.published_at),
            "sentiment": (r.sentiment_manual or r.sentiment) if r else None,
            "sentiment_reason": r.sentiment_reason if r else None,
            "sentiment_manual": r.sentiment_manual if r else None,
            "sentiment_ai": r.sentiment if r else None,
            "topics": _loads(r.topics_json) if r else [],
            "bugs": _loads(r.bugs_json) if r else [],
            "suggestions": _loads(r.suggestions_json) if r else [],
            "content_reviews": _loads(r.content_reviews_json) if r else [],
            "raw_url": p.raw_url,
            "like_count": p.like_count,
            "reply_count": p.reply_count,
            "is_deleted": p.is_deleted,
        })
    return items


def negative_library(session: Session, *, community_id: Optional[int] = None, limit: int = 200) -> list[dict]:
    """负面库：仅包含情绪为 negative 的帖子。"""
    return content_library(session, community_id=community_id, sentiment="negative", limit=limit)
