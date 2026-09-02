from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from sqlmodel import Session, select

from app.core.models import (
    AnalysisAttempt,
    AnalysisResult,
    Post,
    PostStatus,
)
from app.core.tz import now_cn
from app.analyzer.analyzer import AnalysisError, SinglePostAnalyzer
from app.analyzer.parser import AnalysisPayload, payload_to_db_json


def persist_analysis_result(session: Session, post: Post, payload: AnalysisPayload) -> AnalysisResult:
    """落库分析结果，并将 post 状态置为 analyzed。"""
    fields = payload_to_db_json(payload)
    existing = session.exec(
        select(AnalysisResult).where(AnalysisResult.post_id == post.id)
    ).first()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        existing.analyzed_at = now_cn()
        session.add(existing)
    else:
        result = AnalysisResult(post_id=post.id, analyzed_at=now_cn(), **fields)
        session.add(result)

    post.status = PostStatus.ANALYZED
    session.add(post)
    session.commit()
    session.refresh(post)
    existing = session.exec(
        select(AnalysisResult).where(AnalysisResult.post_id == post.id)
    ).first()
    return existing


def record_analysis_failure(
    session: Session, post: Post, error: str, *, max_attempts: int
) -> bool:
    """记录失败尝试。返回是否应跳过该帖（达到 max_attempts）。

    attempt.status: retryable（未达上限，可重试）/ abandoned（已达上限，放弃）
    达到上限时 Post.status 置 failed。
    """
    att = session.exec(
        select(AnalysisAttempt).where(AnalysisAttempt.post_id == post.id)
    ).first()
    if att is None:
        att = AnalysisAttempt(post_id=post.id, attempt_count=0, last_error="", last_at=now_cn())
    att.attempt_count += 1
    att.last_error = error[:2000]
    att.last_at = now_cn()

    if att.attempt_count >= max_attempts:
        att.status = "abandoned"
        post.status = PostStatus.FAILED
        session.add(post)
        session.add(att)
        session.commit()
        return True
    att.status = "retryable"
    session.add(att)
    session.commit()
    return False


def reset_posts_for_reanalysis(session: Session, community_id: int, since=None, until=None) -> int:
    """将指定社区/时间范围内的帖子重置为待分析状态，返回受影响行数。"""
    stmt = select(Post).where(Post.community_id == community_id)
    if since is not None:
        stmt = stmt.where(Post.published_at >= since)
    if until is not None:
        stmt = stmt.where(Post.published_at <= until)
    posts = session.exec(stmt).all()
    count = 0
    for p in posts:
        if p.status != PostStatus.PENDING:
            p.status = PostStatus.PENDING
            session.add(p)
            count += 1
    session.commit()
    return count


def fetch_pending_posts(session: Session, community_id: int | None, batch_size: int) -> list[Post]:
    stmt = select(Post).where(Post.status == PostStatus.PENDING)
    if community_id is not None:
        stmt = stmt.where(Post.community_id == community_id)
    stmt = stmt.limit(batch_size)
    return list(session.exec(stmt).all())


def analyze_post(
    session: Session,
    post: Post,
    analyzer: SinglePostAnalyzer,
    *,
    max_attempts: int,
) -> bool:
    """分析单帖，处理成功/失败。返回是否成功。"""
    try:
        payload = analyzer.analyze(post.title, post.content)
        persist_analysis_result(session, post, payload)
        return True
    except (AnalysisError, Exception) as exc:
        record_analysis_failure(session, post, str(exc), max_attempts=max_attempts)
        return False
