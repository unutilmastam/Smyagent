"""Application settings loaded from environment variables (and `.env` locally)."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_SECRET_LENGTH = 32
_PLACEHOLDER_SECRETS = {"changeme", "change-me", "secret", "dev", "development"}


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ConfigurationError(RuntimeError):
    """Raised when settings are invalid. Messages never contain secret values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Environment = Environment.DEVELOPMENT
    app_name: str = "SMY Agent"
    app_secret_key: SecretStr = SecretStr("")
    app_base_url: str = "http://localhost:8000"

    database_url: SecretStr = SecretStr("sqlite:///./smy_agent.db")

    ai_provider: str = ""
    ai_api_key: SecretStr = SecretStr("")
    ai_model_small: str = ""
    ai_model_large: str = ""

    search_provider: str = ""
    search_api_key: SecretStr = SecretStr("")

    telegram_admin_bot_token: SecretStr = SecretStr("")
    telegram_client_bot_token: SecretStr = SecretStr("")
    telegram_webhook_secret: SecretStr = SecretStr("")
    telegram_admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    outbound_sending_enabled: bool = False
    log_level: str = "INFO"
    daily_ai_budget_usd: float = Field(default=0.0, ge=0)
    daily_search_limit: int = Field(default=0, ge=0)
    default_timezone: str = "Asia/Tashkent"

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            if not all(p.isdigit() for p in parts):
                raise ValueError("must be comma-separated numeric Telegram user IDs")
            return [int(p) for p in parts]
        if isinstance(value, int):
            return [value]
        return value

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return upper

    @field_validator("default_timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.app_env is not Environment.PRODUCTION:
            return self
        secret = self.app_secret_key.get_secret_value()
        if len(secret) < MIN_SECRET_LENGTH or secret.lower() in _PLACEHOLDER_SECRETS:
            raise ValueError(
                f"APP_SECRET_KEY must be set to at least {MIN_SECRET_LENGTH} random characters "
                "in production"
            )
        if self.database_url.get_secret_value().startswith("sqlite"):
            raise ValueError("DATABASE_URL must point to MySQL/MariaDB in production, not SQLite")
        if self.ai_provider and not self.ai_api_key.get_secret_value():
            raise ValueError("AI_API_KEY is required when AI_PROVIDER is set")
        if self.search_provider and not self.search_api_key.get_secret_value():
            raise ValueError("SEARCH_API_KEY is required when SEARCH_PROVIDER is set")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env is Environment.PRODUCTION


def load_settings(**overrides: object) -> Settings:
    """Build settings, converting validation errors into a secret-free message."""
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        problems = []
        for err in exc.errors(include_input=False, include_url=False):
            field = ".".join(str(p) for p in err["loc"]).upper() or "SETTINGS"
            problems.append(f"- {field}: {err['msg']}")
        raise ConfigurationError("Invalid configuration:\n" + "\n".join(problems)) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
