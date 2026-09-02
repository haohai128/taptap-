from __future__ import annotations

from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def to_cn(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CN_TZ)
    return dt.astimezone(CN_TZ)


def iso_cn(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return to_cn(dt).isoformat()
