from __future__ import annotations

import io
from typing import ClassVar

import pytest
from sqlalchemy import select

from app import cli
from app.core.config import get_settings
from app.core.security import verify_password
from app.domain.auth import Role
from app.infrastructure.database import Database
from app.infrastructure.database.models import User


@pytest.fixture
def cli_env(monkeypatch: pytest.MonkeyPatch, database_url: str, db: Database) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()


def _run(monkeypatch: pytest.MonkeyPatch, args: list[str], stdin: str) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return cli.main(args)


def test_create_owner_once(
    cli_env: None, monkeypatch: pytest.MonkeyPatch, db: Database, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["create-owner", "--username", "Bahrullo", "--password-stdin"]
    assert _run(monkeypatch, args, "Strong-Pass-2026!\n") == 0
    with db.transaction() as s:
        user = s.scalars(select(User)).one()
        assert user.username == "bahrullo" and user.role is Role.OWNER
        assert verify_password(user.password_hash, "Strong-Pass-2026!")
        assert "Strong-Pass-2026!" not in user.password_hash

    assert _run(monkeypatch, args, "Another-Pass-2026!\n") == 1
    assert "already exists" in capsys.readouterr().err


def test_create_owner_rejects_weak_password(
    cli_env: None, monkeypatch: pytest.MonkeyPatch, db: Database
) -> None:
    assert (
        _run(monkeypatch, ["create-owner", "--username", "x_owner", "--password-stdin"], "short\n")
        == 1
    )
    with db.transaction() as s:
        assert s.scalars(select(User)).first() is None


def test_check_config(cli_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["check-config"]) == 0
    assert "Database reachable: yes" in capsys.readouterr().out


class _FakeTelegram:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def __init__(self, token: str) -> None:
        self.token = token

    def set_webhook(self, url: str, *, secret_token: str) -> None:
        self.calls.append(("set_webhook", {"url": url, "secret": secret_token}))

    def webhook_info(self) -> dict[str, object]:
        return {
            "url": "https://agent.example.uz/api/v1/telegram/webhook",
            "pending_update_count": 0,
        }


@pytest.fixture
def bot_env(monkeypatch: pytest.MonkeyPatch, database_url: str, db: Database) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("TELEGRAM_ADMIN_BOT_TOKEN", "1234567890:AAH" + "x" * 32)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "w" * 40)
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "5000001")
    monkeypatch.setattr(cli, "TelegramClient", _FakeTelegram)
    _FakeTelegram.calls = []
    get_settings.cache_clear()


def test_telegram_set_webhook_requires_https(
    bot_env: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("APP_BASE_URL", "http://agent.example.uz")
    get_settings.cache_clear()
    assert cli.main(["telegram-set-webhook"]) == 1
    assert "https" in capsys.readouterr().err
    assert _FakeTelegram.calls == []


def test_telegram_set_webhook_and_info(
    bot_env: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://agent.example.uz/")
    get_settings.cache_clear()
    assert cli.main(["telegram-set-webhook"]) == 0
    assert _FakeTelegram.calls == [
        (
            "set_webhook",
            {"url": "https://agent.example.uz/api/v1/telegram/webhook", "secret": "w" * 40},
        )
    ]
    assert cli.main(["telegram-webhook-info"]) == 0
    out = capsys.readouterr().out
    assert "pending_update_count: 0" in out
    assert "1234567890:AAH" not in out


def test_telegram_commands_need_configuration(
    cli_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["telegram-webhook-info"]) == 1
    assert "TELEGRAM_ADMIN_BOT_TOKEN" in capsys.readouterr().err
