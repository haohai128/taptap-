from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """配置缺失或非法时抛出。"""


REQUIRED_AI_ENV_VARS = ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class CollectorConfig:
    min_request_interval_seconds: float = 2.0
    max_retries: int = 3
    per_run_limit_default: int = 50
    schedule_interval_seconds_default: int = 3600


@dataclass
class AnalyzerConfig:
    batch_size: int = 20
    poll_interval_seconds: int = 30
    max_attempts: int = 3


@dataclass
class DatabaseConfig:
    url: str = "sqlite:///./data/app.db"


@dataclass
class PlatformConfig:
    """平台级限速退避配置。未指定时由 collector 段默认值兜底。"""
    min_request_interval_seconds: float = 2.0
    max_retries: int = 3
    backoff_factor: float = 2.0
    backoff_cap_seconds: float = 60.0
    max_requests_per_run: int = 200
    max_concurrency: int = 1


@dataclass
class AIConfig:
    base_url: str
    api_key: str
    model: str


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    analyzer: AnalyzerConfig = field(default_factory=AnalyzerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ai: AIConfig | None = None
    platforms: dict[str, "PlatformConfig"] = field(default_factory=dict)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件 {path} 顶层应为映射/dict")
    return data


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"无法将 {value!r} 转为 int") from exc


def _coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"无法将 {value!r} 转为 float") from exc


def _build_server(raw: dict[str, Any]) -> ServerConfig:
    return ServerConfig(
        host=str(raw.get("host", "127.0.0.1")),
        port=_coerce_int(raw.get("port"), 8000),
    )


def _build_collector(raw: dict[str, Any]) -> CollectorConfig:
    return CollectorConfig(
        min_request_interval_seconds=_coerce_float(raw.get("min_request_interval_seconds"), 2.0),
        max_retries=_coerce_int(raw.get("max_retries"), 3),
        per_run_limit_default=_coerce_int(raw.get("per_run_limit_default"), 50),
        schedule_interval_seconds_default=_coerce_int(raw.get("schedule_interval_seconds_default"), 3600),
    )


def _build_analyzer(raw: dict[str, Any]) -> AnalyzerConfig:
    return AnalyzerConfig(
        batch_size=_coerce_int(raw.get("batch_size"), 20),
        poll_interval_seconds=_coerce_int(raw.get("poll_interval_seconds"), 30),
        max_attempts=_coerce_int(raw.get("max_attempts"), 3),
    )


def _build_database(raw: dict[str, Any]) -> DatabaseConfig:
    return DatabaseConfig(url=str(raw.get("url", "sqlite:///./data/app.db")))


def _build_ai() -> AIConfig:
    missing = [name for name in REQUIRED_AI_ENV_VARS if not os.getenv(name)]
    if missing:
        raise ConfigError(
            "缺少必要的 AI 环境变量: " + ", ".join(missing) +
            "。请设置 OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL 后再启动。"
        )
    return AIConfig(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.environ["OPENAI_MODEL"],
    )


def _build_platforms(raw: dict[str, Any]) -> dict[str, PlatformConfig]:
    """解析 platforms 段，每项为 PlatformConfig。未出现的字段走默认值。"""
    out: dict[str, PlatformConfig] = {}
    if not isinstance(raw, dict):
        return out
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        out[name] = PlatformConfig(
            min_request_interval_seconds=_coerce_float(cfg.get("min_request_interval_seconds"), 2.0),
            max_retries=_coerce_int(cfg.get("max_retries"), 3),
            backoff_factor=_coerce_float(cfg.get("backoff_factor"), 2.0),
            backoff_cap_seconds=_coerce_float(cfg.get("backoff_cap_seconds"), 60.0),
            max_requests_per_run=_coerce_int(cfg.get("max_requests_per_run"), 200),
            max_concurrency=_coerce_int(cfg.get("max_concurrency"), 1),
        )
    return out


def load_config(path: str | Path = "config.yaml", require_ai: bool = True) -> AppConfig:
    raw = _load_yaml(Path(path))
    config = AppConfig(
        server=_build_server(raw.get("server", {})),
        collector=_build_collector(raw.get("collector", {})),
        analyzer=_build_analyzer(raw.get("analyzer", {})),
        database=_build_database(raw.get("database", {})),
        platforms=_build_platforms(raw.get("platforms", {})),
    )
    if require_ai:
        config.ai = _build_ai()
    return config
