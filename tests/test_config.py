from app.core.config import load_config


def test_config_defaults_no_ai():
    config = load_config(require_ai=False)
    assert config.server.port == 8000
    assert config.collector.per_run_limit_default == 50
    assert config.ai is None


def test_config_ai_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://x/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_MODEL", "m")
    config = load_config(require_ai=True)
    assert config.ai is not None
    assert config.ai.base_url == "http://x/v1"
    assert config.ai.model == "m"
