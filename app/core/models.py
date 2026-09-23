from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel

from app.core.tz import now_cn


def _utcnow() -> datetime:
    return now_cn()


class PostStatus(str, Enum):
    PENDING = "pending"
    ANALYZED = "analyzed"
    FAILED = "failed"


class CollectionRunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    AUTH_EXPIRED = "auth_expired"
    NETWORK_ERROR = "network_error"
    STOPPED = "stopped"


class CollectStatus(str, Enum):
    ENABLED = "enabled"
    STOPPED = "stopped"


class CollectorErrorType(str, Enum):
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    AUTH_EXPIRED = "auth_expired"
    NETWORK_ERROR = "network_error"
    HTTP_ERROR = "http_error"


class AlertLevel(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class KeywordCategory(str, Enum):
    NEGATIVE = "negative"    # 负面库关键词
    EXCLUDE = "exclude"      # 排除词


class Platform(str, Enum):
    TAPTAP = "taptap"


class ReviewStatus(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"


class Community(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    taptap_id: str = Field(index=True, unique=True)
    name: str = ""
    raw_url: str = ""
    platform: str = Field(default=Platform.TAPTAP.value, index=True)
    platform_id: str = Field(default="", index=True)
    group_id: Optional[str] = Field(default=None)
    enabled: bool = True
    collect_status: str = Field(default=CollectStatus.ENABLED.value, index=True)
    interval_seconds: int = 3600
    per_run_limit: int = 50
    created_at: datetime = Field(default_factory=_utcnow)


class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    community_id: int = Field(foreign_key="community.id", index=True)
    taptap_post_id: str = Field(index=True, unique=True)
    platform: str = Field(default=Platform.TAPTAP.value, index=True)
    title: str = ""
    content: str = ""
    author: str = ""
    published_at: Optional[datetime] = None
    reply_count: int = 0
    like_count: int = 0
    raw_url: str = ""
    status: PostStatus = Field(default=PostStatus.PENDING, index=True)
    fetched_at: datetime = Field(default_factory=_utcnow)
    topic_id: str = ""
    is_elite: bool = False
    is_official: bool = False
    group_id: str = ""
    is_deleted: bool = Field(default=False, index=True)


class AnalysisResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="post.id", unique=True)
    topics_json: str = "[]"
    sentiment: str = "unknown"
    sentiment_reason: str = ""
    bugs_json: str = "[]"
    suggestions_json: str = "[]"
    content_reviews_json: str = "[]"
    analyzed_at: datetime = Field(default_factory=_utcnow)


class CollectionRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    community_id: int = Field(foreign_key="community.id", index=True)
    started_at: datetime = Field(default_factory=_utcnow)
    ended_at: Optional[datetime] = None
    fetched_count: int = 0
    new_count: int = 0
    failed_count: int = 0
    error: str = ""
    status: CollectionRunStatus = Field(default=CollectionRunStatus.RUNNING)
    last_request_at: Optional[datetime] = None
    error_type: Optional[str] = None


class AnalysisAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="post.id", index=True)
    attempt_count: int = 0
    last_error: str = ""
    last_at: datetime = Field(default_factory=_utcnow)
    status: str = Field(default="retryable")


class Keyword(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    word: str = Field(index=True)
    category: str = Field(default=KeywordCategory.NEGATIVE.value, index=True)
    enabled: bool = True
    created_at: datetime = Field(default_factory=_utcnow)


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: Optional[int] = Field(default=None, foreign_key="post.id", index=True)
    community_id: Optional[int] = Field(default=None, foreign_key="community.id", index=True)
    level: str = Field(default=AlertLevel.WARN.value, index=True)
    status: str = Field(default=AlertStatus.OPEN.value, index=True)
    title: str = ""
    detail: str = ""
    keyword: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = None


class Briefing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = ""
    period_start: datetime = Field(default_factory=_utcnow)
    period_end: datetime = Field(default_factory=_utcnow)
    summary: str = ""
    stats_json: str = "{}"
    created_at: datetime = Field(default_factory=_utcnow)


class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="post.id", unique=True, index=True)
    analysis_result_id: Optional[int] = Field(default=None, foreign_key="analysisresult.id")
    status: str = Field(default=ReviewStatus.CORRECT.value, index=True)
    sentiment_correct: bool = True
    bugs_correct: bool = True
    suggestions_correct: bool = True
    topics_correct: bool = True
    content_reviews_correct: bool = True
    corrected_sentiment: str = ""
    corrected_bugs_json: str = "[]"
    corrected_suggestions_json: str = "[]"
    corrected_topics_json: str = "[]"
    corrected_content_reviews_json: str = "[]"
    reviewed_at: datetime = Field(default_factory=_utcnow)
