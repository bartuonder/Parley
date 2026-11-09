import pytest
from pydantic import ValidationError

from parley.settings import Settings, get_settings

DB_URL = "postgresql://user:pw@localhost:5432/parley"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("ENV", "LOG_LEVEL", "DATABASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(f"PARLEY_{key}", raising=False)
    get_settings.cache_clear()


def build(**overrides: str) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_defaults_with_required_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    settings = build()
    assert settings.env == "dev"
    assert settings.log_level == "INFO"
    assert settings.llm_api_key is None
    assert str(settings.database_url) == DB_URL


def test_missing_database_url_fails() -> None:
    with pytest.raises(ValidationError):
        build()


def test_invalid_env_value_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    monkeypatch.setenv("PARLEY_ENV", "staging")
    with pytest.raises(ValidationError):
        build()


def test_secret_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    monkeypatch.setenv("PARLEY_LLM_API_KEY", "sk-secret")
    settings = build()
    assert "sk-secret" not in repr(settings)
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "sk-secret"


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    assert get_settings() is get_settings()
