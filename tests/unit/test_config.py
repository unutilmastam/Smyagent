from __future__ import annotations

import pytest

from app.core.config import ConfigurationError, Environment, load_settings

SECRET_VALUE = "super-secret-value-that-must-not-leak"


def test_defaults_are_safe() -> None:
    s = load_settings(_env_file=None)
    assert s.app_env is Environment.TEST  # set by conftest via env
    assert s.outbound_sending_enabled is False
    assert s.telegram_admin_ids == []
    assert s.default_timezone == "Asia/Tashkent"


def test_admin_ids_parsed_from_comma_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "123456, 7890")
    s = load_settings(_env_file=None)
    assert s.telegram_admin_ids == [123456, 7890]


def test_admin_ids_reject_usernames(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "@ITcoDe_Uz")
    with pytest.raises(ConfigurationError, match="TELEGRAM_ADMIN_IDS"):
        load_settings(_env_file=None)


def test_production_requires_strong_secret() -> None:
    with pytest.raises(ConfigurationError, match="APP_SECRET_KEY"):
        load_settings(
            _env_file=None,
            app_env="production",
            app_secret_key="short",
            database_url="mysql+pymysql://u:p@h/db",
        )


def test_production_rejects_sqlite() -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_settings(
            _env_file=None,
            app_env="production",
            app_secret_key="y" * 40,
            app_base_url="https://agent.example.uz",
        )


def test_production_requires_https_base_url() -> None:
    with pytest.raises(ConfigurationError, match="APP_BASE_URL"):
        load_settings(
            _env_file=None,
            app_env="production",
            app_secret_key="y" * 40,
            app_base_url="http://agent.example.uz",
            database_url="mysql+pymysql://u:p@h/db",
        )


def test_production_requires_ai_key_when_provider_set() -> None:
    with pytest.raises(ConfigurationError, match="AI_API_KEY"):
        load_settings(
            _env_file=None,
            app_env="production",
            app_secret_key="y" * 40,
            app_base_url="https://agent.example.uz",
            database_url="mysql+pymysql://u:p@h/db",
            ai_provider="anthropic",
        )


def test_error_message_never_contains_secret_values() -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(
            _env_file=None,
            app_env="production",
            app_secret_key=SECRET_VALUE[:10],
            database_url=f"mysql+pymysql://u:{SECRET_VALUE}@h/db",
            telegram_admin_ids="not-a-number",
        )
    text = str(exc_info.value)
    assert SECRET_VALUE not in text
    assert SECRET_VALUE[:10] not in text


def test_secrets_hidden_in_repr(prod_settings: object) -> None:
    assert "x" * 48 not in repr(prod_settings)


def test_invalid_timezone_rejected() -> None:
    with pytest.raises(ConfigurationError, match="DEFAULT_TIMEZONE"):
        load_settings(_env_file=None, default_timezone="Mars/Olympus")
