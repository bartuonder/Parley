from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from parley.settings import PROJECT_ROOT, Settings, get_settings

DB_URL = "postgresql://user:pw@localhost:5432/parley"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("ENV", "LOG_LEVEL", "DATABASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(f"PARLEY_{key}", raising=False)
    get_settings.cache_clear()


def build() -> Settings:
    return Settings(_env_file=None)


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


def test_fixed_now_defaults_to_none_and_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    assert build().fixed_now is None
    monkeypatch.setenv("PARLEY_FIXED_NOW", "2026-06-01T12:00:00+00:00")
    assert build().fixed_now == datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def test_pinned_clock_is_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    monkeypatch.setenv("PARLEY_FIXED_NOW", "2026-06-01T12:00:00+00:00")
    monkeypatch.setenv("PARLEY_ENV", "prod")
    with pytest.raises(ValidationError, match="FIXED_NOW"):
        build()
    monkeypatch.setenv("PARLEY_ENV", "dev")
    assert build().fixed_now is not None


def test_model_cache_dir_defaults_to_an_absolute_path_in_the_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    monkeypatch.delenv("PARLEY_MODEL_CACHE_DIR", raising=False)
    path = build().model_cache_dir
    assert path.is_absolute()
    assert path == PROJECT_ROOT / ".cache" / "models"


def test_relative_model_cache_dir_is_resolved_against_the_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    monkeypatch.setenv("PARLEY_MODEL_CACHE_DIR", "somewhere/models")
    monkeypatch.chdir(tmp_path)
    assert build().model_cache_dir == PROJECT_ROOT / "somewhere" / "models"
    monkeypatch.setenv("PARLEY_MODEL_CACHE_DIR", str(tmp_path / "abs"))
    assert build().model_cache_dir == tmp_path / "abs"


def test_dotenv_path_does_not_depend_on_the_working_directory() -> None:
    assert Settings.model_config["env_file"] == PROJECT_ROOT / ".env"


def test_agent_limits_have_defaults_and_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    settings = build()
    assert settings.agent_model == "gpt-4.1-mini"
    assert settings.agent_max_steps == 10
    assert settings.agent_max_cost_usd == 0.25
    monkeypatch.setenv("PARLEY_AGENT_MAX_STEPS", "0")
    with pytest.raises(ValidationError):
        build()


def test_router_model_and_revision_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARLEY_DATABASE_URL", DB_URL)
    settings = build()
    assert settings.router_model == "gpt-4o-mini"
    assert settings.agent_max_revisions == 2
    monkeypatch.setenv("PARLEY_AGENT_MAX_REVISIONS", "9")
    with pytest.raises(ValidationError):
        build()
