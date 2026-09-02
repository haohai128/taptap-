from __future__ import annotations

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event

from app.core.config import AppConfig


_engine = None


def _ensure_parent_dir(url: str) -> None:
    """对 sqlite 文件型 URL 确保父目录存在。"""
    if not url.startswith("sqlite:///"):
        return
    path_part = url[len("sqlite:///"):]
    if path_part.startswith(":memory:") or path_part == "":
        return
    from pathlib import Path

    db_path = Path(path_part)
    if db_path.parent and not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)


def _build_engine(config: AppConfig):
    url = config.database.url
    _ensure_parent_dir(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, echo=False)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_wal(dbapi_conn, _):
            try:
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
            except Exception:
                pass

    return engine


def init_engine(config: AppConfig):
    global _engine
    if _engine is None:
        _engine = _build_engine(config)
    return _engine


def get_engine():
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化，请先调用 init_engine()")
    return _engine


def create_all():
    """根据 SQLModel 元数据创建全部表。用于测试与首次启动兜底。"""
    import app.core.models  # noqa: F401  确保模型已注册

    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """FastAPI 依赖注入用的会话工厂。"""
    engine = get_engine()
    with Session(engine) as session:
        yield session
