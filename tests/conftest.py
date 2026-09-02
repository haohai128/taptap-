from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import AppConfig, ServerConfig, CollectorConfig, AnalyzerConfig, DatabaseConfig


@pytest.fixture()
def tmp_db_url(tmp_path) -> str:
    db_file = tmp_path / "test.db"
    return f"sqlite:///{db_file.as_posix()}"


@pytest.fixture()
def app_config(tmp_db_url) -> AppConfig:
    return AppConfig(
        server=ServerConfig(),
        collector=CollectorConfig(),
        analyzer=AnalyzerConfig(),
        database=DatabaseConfig(url=tmp_db_url),
        ai=None,
    )


@pytest.fixture()
def db_session(app_config) -> Iterator[Session]:
    engine = create_engine(
        app_config.database.url,
        connect_args={"check_same_thread": False},
    )
    import app.core.models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _ai_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    yield
