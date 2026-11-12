from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PARLEY_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: PostgresDsn
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    agent_model: str = "gpt-4.1-mini"
    agent_max_steps: int = Field(default=10, ge=1, le=30)
    agent_max_cost_usd: float = Field(default=0.25, gt=0)
    router_model: str = "gpt-4o-mini"
    agent_max_revisions: int = Field(default=2, ge=0, le=5)
    fixed_now: datetime | None = None
    model_cache_dir: Path = PROJECT_ROOT / ".cache" / "models"

    @field_validator("model_cache_dir")
    @classmethod
    def anchor_to_project_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @model_validator(mode="after")
    def no_pinned_clock_in_prod(self) -> Self:
        if self.env == "prod" and self.fixed_now is not None:
            raise ValueError("PARLEY_FIXED_NOW must not be set when PARLEY_ENV is prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
