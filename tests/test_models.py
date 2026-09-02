from app.core.models import Community, Post, PostStatus


def test_models_create(db_session):
    c = Community(taptap_id="g1", name="Game One", raw_url="https://taptap.cn/app/1")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    p = Post(community_id=c.id, taptap_post_id="p1", title="hello", content="body")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    assert p.id is not None
    assert p.status == PostStatus.PENDING
    assert c.taptap_id == "g1"
