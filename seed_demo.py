"""Seed demo data for evaluation feature: 5 posts with mock analysis results."""
import json
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.core.config import load_config
from app.core.db import init_engine, get_engine
from app.core.models import Community, Post, AnalysisResult, PostStatus

init_engine(load_config(require_ai=False))

mock_analyses = [
    {
        "topics": ["平衡性", "氪金"],
        "sentiment": "negative",
        "sentiment_reason": "玩家普遍抱怨英雄强度失衡与抽卡概率低",
        "bugs": [{"summary": "战斗结束闪退", "impact": "高"}],
        "suggestions": [{"summary": "增加保底机制", "category": "数值"}],
        "content_reviews": [{"subject": "英雄A", "sentiment": "negative", "summary": "强度过高需削弱"}],
    },
    {
        "topics": ["玩法", "社交"],
        "sentiment": "positive",
        "sentiment_reason": "玩家认可阵营玩法创新与好友互动体验",
        "bugs": [],
        "suggestions": [{"summary": "增加更多阵营地图", "category": "玩法"}],
        "content_reviews": [{"subject": "阵营战", "sentiment": "positive", "summary": "策略性强体验好"}],
    },
    {
        "topics": ["BUG", "性能"],
        "sentiment": "negative",
        "sentiment_reason": "玩家反馈加载缓慢与卡顿严重",
        "bugs": [{"summary": "加载界面卡死", "impact": "中"}, {"summary": "帧率波动大", "impact": "中"}],
        "suggestions": [],
        "content_reviews": [{"subject": "客户端性能", "sentiment": "negative", "summary": "低端机体验差"}],
    },
    {
        "topics": ["活动", "奖励"],
        "sentiment": "neutral",
        "sentiment_reason": "活动奖励尚可但玩法缺乏新意",
        "bugs": [],
        "suggestions": [{"summary": "活动玩法多样化", "category": "玩法"}],
        "content_reviews": [],
    },
    {
        "topics": ["平衡性", "新手体验"],
        "sentiment": "negative",
        "sentiment_reason": "新手教程过短且匹配机制不公平",
        "bugs": [{"summary": "新手引导卡进度", "impact": "低"}],
        "suggestions": [{"summary": "延长新手引导", "category": "引导"}, {"summary": "优化匹配算法", "category": "数值"}],
        "content_reviews": [{"subject": "新手引导", "sentiment": "negative", "summary": "信息量不足"}],
    },
]

with Session(get_engine()) as s:
    c = s.exec(select(Community)).first()
    if not c:
        c = Community(taptap_id="app:139029", name="狼人对决", raw_url="https://www.taptap.cn/app/139029/topic", platform="taptap")
        s.add(c); s.commit(); s.refresh(c)
    print("community:", c.id, c.name)

    existing = s.exec(select(Post).where(Post.community_id == c.id)).all()
    if existing:
        print("posts already exist:", len(existing))
    else:
        base = datetime.utcnow() - timedelta(days=2)
        for i in range(5):
            mock = mock_analyses[i]
            p = Post(
                community_id=c.id,
                taptap_post_id=f"demo-post-{i+1}",
                platform="taptap",
                title=f"【玩家反馈{i+1}】关于游戏的几点看法",
                content=f"这是第{i+1}条演示帖子的正文内容，用于展示评估页面。",
                author=f"玩家{i+1}",
                published_at=base + timedelta(hours=i*3),
                reply_count=i*2,
                like_count=i*5,
                raw_url=f"https://www.taptap.cn/moment/{i+1}",
                status=PostStatus.ANALYZED,
                topic_id=f"topic-{i+1}",
            )
            s.add(p); s.commit(); s.refresh(p)
            ar = AnalysisResult(
                post_id=p.id,
                topics_json=json.dumps(mock["topics"], ensure_ascii=False),
                sentiment=mock["sentiment"],
                sentiment_reason=mock["sentiment_reason"],
                bugs_json=json.dumps(mock["bugs"], ensure_ascii=False),
                suggestions_json=json.dumps(mock["suggestions"], ensure_ascii=False),
                content_reviews_json=json.dumps(mock["content_reviews"], ensure_ascii=False),
            )
            s.add(ar)
        s.commit()
        print("seeded 5 posts + 5 analysis results")

    posts = s.exec(select(Post).where(Post.community_id == c.id)).all()
    results = s.exec(select(AnalysisResult)).all()
    print("posts:", len(posts), "analysis results:", len(results))
