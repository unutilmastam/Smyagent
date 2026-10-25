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


def test_log_file_is_rotated_and_redacted(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json
    import logging
    from logging.handlers import RotatingFileHandler

    from app.core.logging import configure_logging

    target = tmp_path / "runner.log"
    root = logging.getLogger()
    saved = root.handlers[:]
    try:
        configure_logging("INFO", log_file=str(target))
        [handler] = root.handlers
        assert isinstance(handler, RotatingFileHandler) and handler.maxBytes == 1_000_000
        logging.getLogger("app.test").info("token=abc123secret done")
        handler.flush()
        line = json.loads(target.read_text(encoding="utf-8").splitlines()[-1])
        assert line["msg"] == "token=*** done"
    finally:
        for h in root.handlers:
            h.close()
        root.handlers[:] = saved
