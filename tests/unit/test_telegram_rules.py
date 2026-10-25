from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import ConfigurationError, load_settings
from app.domain.telegram import Command, is_owner_message, parse_command
from app.infrastructure.telegram.client import TelegramClient, TelegramError

TOKEN = "1234567890:AAH" + "x" * 32
ADMINS = [111]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/status", Command("status", "")),
        ("/STATUS@SmyAgentBot", Command("status", "")),
        ("/agent research_audit pause", Command("agent", "research_audit pause")),
        ("  /help  ", Command("help", "")),
        ("status", None),
        ("", None),
        (None, None),
        ("/", None),
    ],
)
def test_parse_command(text: str | None, expected: Command | None) -> None:
    assert parse_command(text) == expected


@pytest.mark.parametrize(
    ("sender", "is_bot", "chat", "allowed"),
    [
        (111, False, "private", True),
        (222, False, "private", False),  # not an admin
        (111, False, "group", False),  # admin, but in a group
        (111, True, "private", False),  # bots never command
        (None, False, "private", False),
    ],
)
def test_is_owner_message(sender: int | None, is_bot: bool, chat: str, allowed: bool) -> None:
    assert (
        is_owner_message(sender_id=sender, sender_is_bot=is_bot, chat_type=chat, admin_ids=ADMINS)
        is allowed
    )


def test_webhook_secret_charset_validated_without_leaking() -> None:
    with pytest.raises(ConfigurationError) as exc:
        load_settings(_env_file=None, telegram_webhook_secret="bad secret!")
    assert "bad secret!" not in str(exc.value)
    assert "TELEGRAM_WEBHOOK_SECRET" in str(exc.value)


def _prod(**kw: object) -> None:
    base: dict[str, object] = {
        "_env_file": None,
        "app_env": "production",
        "app_secret_key": "s" * 40,
        "app_base_url": "https://agent.example.uz",
        "database_url": "mysql+pymysql://u:p@h/db",
        "telegram_admin_bot_token": TOKEN,
    }
    base.update(kw)
    load_settings(**base)


def test_production_bot_requires_long_secret_and_admin_ids() -> None:
    with pytest.raises(ConfigurationError, match="TELEGRAM_WEBHOOK_SECRET") as exc:
        _prod(telegram_webhook_secret="short", telegram_admin_ids="111")
    assert TOKEN not in str(exc.value)
    with pytest.raises(ConfigurationError, match="TELEGRAM_ADMIN_IDS"):
        _prod(telegram_webhook_secret="w" * 40)
    _prod(telegram_webhook_secret="w" * 40, telegram_admin_ids="111")


def _client(handler: object) -> TelegramClient:
    return TelegramClient(TOKEN, http=httpx.Client(transport=httpx.MockTransport(handler)))  # type: ignore[arg-type]


def test_set_webhook_sends_secret_and_allowed_updates() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": True})

    _client(handler).set_webhook(
        "https://agent.example.uz/api/v1/telegram/webhook", secret_token="w" * 40
    )
    assert str(seen["path"]).endswith("/setWebhook")
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["secret_token"] == "w" * 40
    assert body["allowed_updates"] == ["message", "callback_query"]


def test_errors_never_contain_the_token() -> None:
    def api_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    def network_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect to {request.url}")

    for handler in (api_error, network_error):
        with pytest.raises(TelegramError) as exc:
            _client(handler).webhook_info()
        assert TOKEN not in str(exc.value)
        assert exc.value.__cause__ is None  # chained exception would carry the URL


def test_client_requires_token() -> None:
    with pytest.raises(TelegramError):
        TelegramClient("")


def test_inline_keyboard_and_callback_schema() -> None:
    from app.application.controls import Button
    from app.infrastructure.telegram.notifier import inline_keyboard
    from app.infrastructure.telegram.schemas import TgUpdate

    markup = inline_keyboard(
        [Button("✅", data="pa:" + "x" * 80), Button("✏️", url="https://a.uz/p/1"), Button("-")]
    )
    row = markup["inline_keyboard"][0]
    assert row[0] == {"text": "✅", "callback_data": "pa:" + "x" * 61}  # ≤ 64 bytes
    assert row[1] == {"text": "✏️", "url": "https://a.uz/p/1"}
    assert len(row) == 2  # a button with neither data nor url is dropped
    update = TgUpdate.model_validate(
        {"update_id": 1, "callback_query": {"id": "q", "from": {"id": 5}, "data": "pa:1"}}
    )
    assert update.callback_query is not None and update.callback_query.from_.id == 5
