from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.core.models import AnalysisResult, Post


def effective_sentiment(r: AnalysisResult) -> str:
    """有效情绪：人工修正优先于 AI 判定。"""
    return r.sentiment_manual or r.sentiment


def _load_results_for_posts(session: Session, post_ids: list[int]) -> dict[int, AnalysisResult]:
    if not post_ids:
        return {}
    results = session.exec(
        select(AnalysisResult).where(AnalysisResult.post_id.in_(post_ids))
    ).all()
    return {r.post_id: r for r in results}


def _query_posts(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[Post]:
    stmt = select(Post).where(Post.community_id == community_id)
    if since is not None:
        stmt = stmt.where(Post.published_at >= since)
    if until is not None:
        stmt = stmt.where(Post.published_at <= until)
    return list(session.exec(stmt).all())


def _query_posts_by_platform(
    session: Session,
    platform: Optional[str] = None,
    community_id: Optional[int] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[Post]:
    stmt = select(Post)
    if community_id:
        stmt = stmt.where(Post.community_id == community_id)
    if platform:
        stmt = stmt.where(Post.platform == platform)
    if since:
        stmt = stmt.where(Post.published_at >= since)
    if until:
        stmt = stmt.where(Post.published_at <= until)
    return list(session.exec(stmt).all())


def sentiment_trend(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, list[dict]]:
    """返回各情绪分类按日期的帖子数量分布。"""
    posts = _query_posts(session, community_id, since, until)
    results = _load_results_for_posts(session, [p.id for p in posts])

    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for p in posts:
        r = results.get(p.id)
        if r is None:
            continue
        day = (p.published_at or p.fetched_at).strftime("%Y-%m-%d")
        buckets[day][effective_sentiment(r)] += 1

    days = sorted(buckets.keys())
    series = {"positive": [], "negative": [], "neutral": [], "unknown": []}
    for day in days:
        c = buckets[day]
        for s in series:
            series[s].append({"date": day, "count": c.get(s, 0)})
    return {"days": days, "series": series}


def topic_heat(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = 50,
) -> list[dict]:
    """返回话题标签按频次排序的列表。"""
    import json

    posts = _query_posts(session, community_id, since, until)
    results = _load_results_for_posts(session, [p.id for p in posts])
    counter: Counter[str] = Counter()
    post_sets: dict[str, set[int]] = defaultdict(set)
    for p in posts:
        r = results.get(p.id)
        if r is None:
            continue
        try:
            topics = json.loads(r.topics_json or "[]")
        except json.JSONDecodeError:
            topics = []
        for t in topics:
            counter[t] += 1
            post_sets[t].add(p.id)

    return [
        {"topic": topic, "count": count, "post_count": len(post_sets[topic])}
        for topic, count in counter.most_common(top_n)
    ]


def bugs_and_suggestions(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, list[dict]]:
    """返回去重后的 BUG 条目与玩家建议条目，标注提及帖子数。"""
    import json

    posts = _query_posts(session, community_id, since, until)
    results = _load_results_for_posts(session, [p.id for p in posts])

    bug_map: dict[tuple[str, str], set[int]] = defaultdict(set)
    sug_map: dict[tuple[str, str], set[int]] = defaultdict(set)

    for p in posts:
        r = results.get(p.id)
        if r is None:
            continue
        try:
            bugs = json.loads(r.bugs_json or "[]")
        except json.JSONDecodeError:
            bugs = []
        try:
            sugs = json.loads(r.suggestions_json or "[]")
        except json.JSONDecodeError:
            sugs = []
        for b in bugs:
            key = (b.get("summary", ""), b.get("impact", ""))
            bug_map[key].add(p.id)
        for s in sugs:
            key = (s.get("summary", ""), s.get("category", ""))
            sug_map[key].add(p.id)

    bugs_list = [
        {"summary": k[0], "impact": k[1], "post_count": len(v)}
        for k, v in sorted(bug_map.items(), key=lambda kv: -len(kv[1]))
    ]
    suggestions_list = [
        {"summary": k[0], "category": k[1], "post_count": len(v)}
        for k, v in sorted(sug_map.items(), key=lambda kv: -len(kv[1]))
    ]
    return {"bugs": bugs_list, "suggestions": suggestions_list}


def content_reviews(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """按被评价对象分组展示评价倾向分布与代表性摘要。"""
    import json

    posts = _query_posts(session, community_id, since, until)
    results = _load_results_for_posts(session, [p.id for p in posts])

    groups: dict[str, dict[str, list]] = defaultdict(lambda: {"positive": [], "negative": [], "neutral": []})
    for p in posts:
        r = results.get(p.id)
        if r is None:
            continue
        try:
            reviews = json.loads(r.content_reviews_json or "[]")
        except json.JSONDecodeError:
            reviews = []
        for rv in reviews:
            subject = rv.get("subject", "")
            sent = rv.get("sentiment", "neutral")
            if sent not in ("positive", "negative", "neutral"):
                sent = "neutral"
            groups[subject][sent].append(rv.get("summary", ""))

    return [
        {
            "subject": subject,
            "positive": len(v["positive"]),
            "negative": len(v["negative"]),
            "neutral": len(v["neutral"]),
            "samples": {
                "positive": v["positive"][:3],
                "negative": v["negative"][:3],
                "neutral": v["neutral"][:3],
            },
        }
        for subject, v in groups.items()
    ]


def sentiment_proportion(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """情感占比：返回各情绪分类的帖子总数与占比。"""
    posts = _query_posts(session, community_id, since, until)
    results = _load_results_for_posts(session, [p.id for p in posts])
    counter: Counter[str] = Counter()
    for p in posts:
        r = results.get(p.id)
        if r is None:
            continue
        counter[effective_sentiment(r)] += 1
    total = sum(counter.values()) or 1
    return [
        {"sentiment": s, "count": counter.get(s, 0), "ratio": round(counter.get(s, 0) / total, 4)}
        for s in ("positive", "negative", "neutral", "unknown")
    ]


def time_distribution(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """时间分布：按发布日期聚合帖子数量。"""
    posts = _query_posts(session, community_id, since, until)
    counter: Counter[str] = Counter()
    for p in posts:
        day = (p.published_at or p.fetched_at).strftime("%Y-%m-%d")
        counter[day] += 1
    days = sorted(counter.keys())
    return [{"date": d, "count": counter[d]} for d in days]


def wordcloud(
    session: Session,
    community_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = 100,
) -> list[dict]:
    """热词云：合并 topics + 帖子正文分词后的高频词。"""
    import json
    import re

    posts = _query_posts(session, community_id, since, until)
    results = _load_results_for_posts(session, [p.id for p in posts])
    counter: Counter[str] = Counter()

    for p in posts:
        r = results.get(p.id)
        if r is not None:
            try:
                topics = json.loads(r.topics_json or "[]")
            except json.JSONDecodeError:
                topics = []
            for t in topics:
                counter[t] += 2  # 话题标签权重更高
        # 正文简单分词（按非汉字字符切分，长度>=2 的片段）
        for token in re.findall(r"[\u4e00-\u9fa5]{2,}", p.title + p.content):
            counter[token] += 1

    return [{"name": w, "value": c} for w, c in counter.most_common(top_n)]


def platform_overview(
    session: Session,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """多平台采集概览：各平台帖子数与情绪分布。"""
    from app.core.models import Community

    platforms = ["taptap"]
    out = []
    for pf in platforms:
        posts = _query_posts_by_platform(session, platform=pf, since=since, until=until)
        results = _load_results_for_posts(session, [p.id for p in posts])
        sent_counter: Counter[str] = Counter()
        for p in posts:
            r = results.get(p.id)
            if r:
                sent_counter[effective_sentiment(r)] += 1
        out.append({
            "platform": pf,
            "post_count": len(posts),
            "sentiments": dict(sent_counter),
        })
    return out


def dashboard_summary(session: Session, days: int = 7) -> dict:
    """看板汇总：KPI、情绪占比、近 N 天趋势、热点话题、最新预警。"""
    from app.core.models import Alert, Community
    from app.core.tz import now_cn

    now = now_cn()
    since = now - __import__("datetime").timedelta(days=days)

    posts = list(session.exec(select(Post).order_by(Post.id.desc())).all())
    results = _load_results_for_posts(session, [p.id for p in posts])

    sent_counter: Counter[str] = Counter()
    deleted_count = 0
    pending_count = 0
    total_likes = 0
    total_replies = 0
    for p in posts:
        if p.is_deleted:
            deleted_count += 1
            continue
        if p.status and p.status.value == "pending":
            pending_count += 1
        total_likes += p.like_count or 0
        total_replies += p.reply_count or 0
        r = results.get(p.id)
        if r:
            sent_counter[effective_sentiment(r)] += 1

    total = len(posts)
    analyzed = sum(sent_counter.values())

    # 近 N 天趋势（按日聚合情绪）
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for p in posts:
        r = results.get(p.id)
        if r is None or p.published_at is None:
            continue
        pub = p.published_at
        if getattr(pub, "tzinfo", None) is not None:
            pub = pub.replace(tzinfo=None)
        try:
            if pub >= since.replace(tzinfo=None):
                buckets[pub.strftime("%Y-%m-%d")][effective_sentiment(r)] += 1
        except TypeError:
            pass
    trend_days = sorted(buckets.keys())
    trend = {
        "days": trend_days,
        "series": {
            s: [{"date": d, "count": buckets[d].get(s, 0)} for d in trend_days]
            for s in ("positive", "negative", "neutral")
        },
    }

    # 热点话题（全部帖子的 topics 频次 top10）
    topic_counter: Counter[str] = Counter()
    for r in results.values():
        try:
            import json as _json
            for t in _json.loads(r.topics_json or "[]"):
                if t:
                    topic_counter[t] += 1
        except Exception:
            pass
    hot_topics = [{"name": t, "count": c} for t, c in topic_counter.most_common(10)]

    # 最新预警（最多 5 条未处理）
    alerts = list(
        session.exec(
            select(Alert).where(Alert.status == "open").order_by(Alert.created_at.desc()).limit(5)
        ).all()
    )
    alert_items = [
        {
            "id": a.id,
            "title": a.title,
            "detail": (a.detail or "")[:120],
            "level": a.level,
            "keyword": a.keyword,
            "created_at": a.created_at,
        }
        for a in alerts
    ]

    return {
        "kpi": {
            "total": total,
            "analyzed": analyzed,
            "pending": pending_count,
            "deleted": deleted_count,
            "positive": sent_counter.get("positive", 0),
            "negative": sent_counter.get("negative", 0),
            "neutral": sent_counter.get("neutral", 0),
            "unknown": sent_counter.get("unknown", 0),
            "total_likes": total_likes,
            "total_replies": total_replies,
        },
        "sentiment_proportion": dict(sent_counter),
        "trend": trend,
        "hot_topics": hot_topics,
        "alerts": alert_items,
    }
