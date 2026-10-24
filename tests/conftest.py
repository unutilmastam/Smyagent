from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Keep tests independent of any developer .env file and real environment.
for _key in list(os.environ):
    if _key.startswith(("APP_", "DATABASE_", "AI_", "SEARCH_", "TELEGRAM_", "DAILY_")) or _key in {
        "LOG_LEVEL",
        "DEFAULT_TIMEZONE",
        "OUTBOUND_SENDING_ENABLED",
    }:
        del os.environ[_key]
os.environ["APP_ENV"] = "test"

from app.core.config import Settings, get_settings, load_settings  # noqa: E402
from app.main import create_app  # noqa: E402

PROD_SECRET = "x" * 48


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return load_settings(_env_file=None, app_env="test", database_url="sqlite://")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.fixture
def prod_settings() -> Settings:
    return load_settings(
        _env_file=None,
        app_env="production",
        app_secret_key=PROD_SECRET,
        app_base_url="https://agent.example.uz",
        database_url="mysql+pymysql://u:p@localhost/smy?charset=utf8mb4",
    )
