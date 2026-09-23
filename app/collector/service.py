from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from app.core.models import (
    CollectionRun,
    CollectionRunStatus,
    CollectorErrorType,
    Community,
    Post,
    PostStatus,
)
from app.core.tz import now_cn
from app.collector.adapter import (
    AntiCrawlError,
    CommunityAdapter,
    CommunityNotAccessibleError,
    FetchedPost,
)
from app.collector.rate_limit import RateLimiter
from app.collector.retry import MaxRetriesExceeded, retry_with_backoff
from app.collector import platform_state
from app.collector import cancel_token
import httpx
import logging

logger = logging.getLogger(__name__)


# 风控类型 → CollectionRun 状态映射
_ERROR_TYPE_TO_RUN_STATUS = {
    CollectorErrorType.BLOCKED: CollectionRunStatus.BLOCKED,
    CollectorErrorType.RATE_LIMITED: CollectionRunStatus.RATE_LIMITED,
    CollectorErrorType.AUTH_EXPIRED: CollectionRunStatus.AUTH_EXPIRED,
    CollectorErrorType.NETWORK_ERROR: CollectionRunStatus.NETWORK_ERROR,
}


class DuplicateCommunityError(RuntimeError):
    def __init__(self, existing: Community):
        self.existing = existing
        super().__init__(f"社区已存在: {existing.taptap_id}")


def register_community(
    session: Session,
    raw_url: str,
    *,
    interval_seconds: int,
    per_run_limit: int,
    adapter: CommunityAdapter,
    name: str = "",
    platform: str = "taptap",
) -> Community:
    community_id = adapter.parse_community_id(raw_url)

    existing = session.exec(select(Community).where(Community.taptap_id == community_id)).first()
    if existing:
        raise DuplicateCommunityError(existing)

    platform_id = ""
    if community_id.startswith("app:"):
        platform_id = community_id.split(":", 1)[1]

    community = Community(
        taptap_id=community_id,
        name=name,
        raw_url=raw_url,
        platform=platform,
        platform_id=platform_id,
        enabled=True,
        interval_seconds=interval_seconds,
        per_run_limit=per_run_limit,
    )
    session.add(community)
    session.commit()
    session.refresh(community)
    return community


def upsert_post(session: Session, community_id: int, fetched: FetchedPost, platform: str = "taptap") -> tuple[Post, bool]:
    """去重入库。返回 (post, created)。

    已存在且发布时间在近 3 天内：更新点赞/回复数等热度字段；
    超过 3 天的旧帖不再更新（热度已稳定，节省写放大）。
    """
    existing = session.exec(
        select(Post).where(Post.taptap_post_id == fetched.taptap_post_id)
    ).first()
    if existing:
        cutoff = now_cn() - timedelta(days=3)
        pub = existing.published_at
        if pub is not None:
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            if pub >= cutoff:
                existing.reply_count = fetched.reply_count
                existing.like_count = fetched.like_count
                session.add(existing)
                session.commit()
                session.refresh(existing)
        return existing, False

    post = Post(
        community_id=community_id,
        taptap_post_id=fetched.taptap_post_id,
        platform=platform,
        title=fetched.title,
        content=fetched.content,
        author=fetched.author,
        published_at=fetched.published_at,
        reply_count=fetched.reply_count,
        like_count=fetched.like_count,
        raw_url=fetched.raw_url,
        status=PostStatus.PENDING,
        topic_id=fetched.topic_id,
        is_elite=fetched.is_elite,
        is_official=fetched.is_official,
        group_id=fetched.group_id,
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    return post, True


def run_collection(
    session: Session,
    community: Community,
    adapter: CommunityAdapter,
    rate_limiter: RateLimiter,
    *,
    max_retries: int = 3,
) -> CollectionRun:
    run = CollectionRun(community_id=community.id, status=CollectionRunStatus.RUNNING)
    session.add(run)
    session.commit()
    session.refresh(run)

    started = now_cn()
    run.started_at = started
    fetched_count = 0
    new_count = 0
    failed_count = 0
    error = ""
    last_request_at: Optional[datetime] = None
    error_type: Optional[str] = None
    platform = community.platform

    platform_state.update_platform_state(platform, platform_state.STATUS_COLLECTING)

    def _classify_exc(exc: Exception) -> Optional[CollectorErrorType]:
        try:
            return adapter.classify_response(exception=exc)
        except Exception:
            return None

    def _finish(status: CollectionRunStatus, err: str = "", etype: Optional[CollectorErrorType] = None) -> None:
        nonlocal error, error_type
        error = err
        if etype is not None:
            error_type = etype.value
        run.status = status
        run.ended_at = now_cn()
        run.fetched_count = fetched_count
        run.new_count = new_count
        run.failed_count = failed_count
        run.error = error[:4000]
        run.last_request_at = last_request_at
        run.error_type = error_type
        session.add(run)
        session.commit()
        session.refresh(run)
        # 更新平台内存状态
        state_map = {
            CollectionRunStatus.BLOCKED: platform_state.STATUS_BLOCKED,
            CollectionRunStatus.RATE_LIMITED: platform_state.STATUS_RATE_LIMITED,
            CollectionRunStatus.AUTH_EXPIRED: platform_state.STATUS_AUTH_EXPIRED,
            CollectionRunStatus.NETWORK_ERROR: platform_state.STATUS_NETWORK_ERROR,
        }
        plat_status = state_map.get(status, platform_state.STATUS_NORMAL)
        platform_state.update_platform_state(platform, plat_status, error=error or None, last_run_at=run.ended_at)

    try:
        fetch_kwargs: dict = {}
        if hasattr(adapter, "fetch_post_list") and community.group_id:
            fetch_kwargs["group_id"] = community.group_id
        list_items = adapter.fetch_post_list(community.taptap_id, community.per_run_limit, **fetch_kwargs)
        last_request_at = now_cn()
    except AntiCrawlError as exc:
        _finish(CollectionRunStatus.BLOCKED, f"anti-crawl: {exc}", CollectorErrorType.BLOCKED)
        return run
    except CommunityNotAccessibleError as exc:
        _finish(CollectionRunStatus.FAILED, f"not-accessible: {exc}")
        return run
    except Exception as exc:
        etype = _classify_exc(exc)
        if etype is not None:
            status = _ERROR_TYPE_TO_RUN_STATUS.get(etype, CollectionRunStatus.FAILED)
            _finish(status, f"fetch_list: {exc}", etype)
        else:
            _finish(CollectionRunStatus.FAILED, f"fetch_list: {exc}")
        return run

    for item in list_items:
        if cancel_token.is_stop_requested(community.id):
            _finish(CollectionRunStatus.STOPPED, "user stopped")
            return run
        rate_limiter.sync_wait(item["raw_url"])
        last_request_at = now_cn()
        fetched_count += 1
        try:
            fetched = retry_with_backoff(
                lambda: adapter.fetch_post_detail(item),
                max_retries=max_retries,
                retriable=lambda e: not isinstance(e, AntiCrawlError),
            )
            _, created = upsert_post(session, community.id, fetched, platform=community.platform)
            if created:
                new_count += 1
        except AntiCrawlError as exc:
            failed_count += 1
            _finish(CollectionRunStatus.BLOCKED, f"anti-crawl during detail: {exc}", CollectorErrorType.BLOCKED)
            return run
        except MaxRetriesExceeded as exc:
            failed_count += 1
            error = (error + "\n" + str(exc)).strip()
        except Exception as exc:
            etype = _classify_exc(exc)
            if etype is not None and etype in (CollectorErrorType.BLOCKED, CollectorErrorType.AUTH_EXPIRED):
                failed_count += 1
                status = _ERROR_TYPE_TO_RUN_STATUS.get(etype, CollectionRunStatus.FAILED)
                _finish(status, f"detail {item.get('taptap_post_id')}: {exc}", etype)
                return run
            failed_count += 1
            error = (error + "\n" + f"post {item.get('taptap_post_id')}: {exc}").strip()

    if list_items and not community.group_id:
        discovered_gid = None
        for it in list_items:
            discovered_gid = it.get("group_id")
            if discovered_gid:
                break
        if discovered_gid:
            community.group_id = str(discovered_gid)
            session.add(community)

    # 删除检测：本次抓到的帖子 id 集合
    fetched_ids = {it.get("taptap_post_id") for it in list_items if it.get("taptap_post_id")}
    # 近 3 天内已入库、但本次列表中已不存在的帖子 → 标记被删除
    if fetched_ids:
        cutoff = now_cn() - timedelta(days=3)
        recent_posts = session.exec(
            select(Post).where(
                Post.community_id == community.id,
                Post.is_deleted == False,  # noqa: E712
            )
        ).all()
        for p in recent_posts:
            if p.published_at is None:
                continue
            pub = p.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            if pub >= cutoff and p.taptap_post_id not in fetched_ids:
                p.is_deleted = True
                session.add(p)
        # 帖子重新出现（作者撤销删除）→ 恢复正常
        for p in session.exec(
            select(Post).where(Post.community_id == community.id, Post.is_deleted == True)  # noqa: E712
        ).all():
            if p.taptap_post_id in fetched_ids:
                p.is_deleted = False
                session.add(p)

    if run.status == CollectionRunStatus.RUNNING:
        if failed_count > 0:
            final_status = CollectionRunStatus.PARTIAL
        else:
            final_status = CollectionRunStatus.SUCCESS
        _finish(final_status)
    else:
        session.add(run)
        session.commit()
        session.refresh(run)
    return run
