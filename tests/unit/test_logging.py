from __future__ import annotations

import json
import logging

from app.core.logging import REDACTED, JsonFormatter, redact, redact_text, request_id_var

BOT_TOKEN = "1234567890:AAH" + "a" * 32


def _format(record: logging.LogRecord) -> dict[str, object]:
    return json.loads(JsonFormatter().format(record))


def test_redacts_telegram_bot_token_in_message() -> None:
    assert BOT_TOKEN not in redact_text(f"calling bot{BOT_TOKEN}/sendMessage")


def test_redacts_inline_key_value() -> None:
    out = redact_text("api_key=sk-live-123 password: hunter2")
    assert "sk-live-123" not in out and "hunter2" not in out


def test_redacts_url_credentials() -> None:
    out = redact_text("mysql+pymysql://smy:p4ss@localhost/db")
    assert "p4ss" not in out
    assert "smy:" + REDACTED + "@localhost" in out


def test_redacts_sensitive_keys_recursively() -> None:
    data = {"headers": {"Authorization": "Bearer abc"}, "user": "ok", "api_key": "k"}
    out = redact(data)
    assert out["headers"]["Authorization"] == REDACTED
    assert out["api_key"] == REDACTED
    assert out["user"] == "ok"


def test_formatter_outputs_json_with_request_id_and_redaction() -> None:
    token = request_id_var.set("req-12345678")
    try:
        record = logging.makeLogRecord(
            {"name": "t", "levelname": "INFO", "msg": "hello", "token": "secret-xyz"}
        )
        payload = _format(record)
    finally:
        request_id_var.reset(token)
    assert payload["msg"] == "hello"
    assert payload["request_id"] == "req-12345678"
    assert payload["token"] == REDACTED
