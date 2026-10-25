"""scripts/setup_env.py: the server .env the owner creates from cPanel Terminal."""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from app.core.config import load_settings

ROOT = Path(__file__).resolve().parents[2]


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("setup_env", ROOT / "scripts" / "setup_env.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["setup_env"] = module
    spec.loader.exec_module(module)
    return module


env = _module()
EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
TOKEN_A = "123456789:AAH" + "x" * 32
TOKEN_B = "987654321:AAC" + "y" * 32
HARD_PASSWORD = "P@ss#w0rd$x/1 ok%"


def _answers(*values: str) -> Any:
    queue = list(values)

    def ask(question: str, default: str, hidden: bool) -> str:
        return queue.pop(0)

    return ask


def test_database_url_encodes_special_characters() -> None:
    url = env.database_url("cpu_smyagent", "cpu_smy", HARD_PASSWORD)
    assert url == (
        "mysql+pymysql://cpu_smy:P%40ss%23w0rd%24x%2F1%20ok%25@localhost/cpu_smyagent"
        "?charset=utf8mb4"
    )
    with pytest.raises(env.SetupError):
        env.database_url("bad name", "u", "p")
    with pytest.raises(env.SetupError):
        env.database_url("db", "u", "")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("TELEGRAM_ADMIN_BOT_TOKEN", "not-a-token"),
        ("TELEGRAM_ADMIN_IDS", "@bahrullo"),
        ("APP_BASE_URL", "http://agent.itcode.uz"),
        ("SMTP_PASSWORD", "two\nlines"),
        ("SMTP_PASSWORD", "it's"),
        ("SMTP_PASSWORD", "pa${HOME}ss"),  # the .env reader would expand it
    ],
)
def test_validation(key: str, value: str) -> None:
    with pytest.raises(env.SetupError):
        env.validate(key, value)


def test_ids_are_normalized() -> None:
    assert env.validate("TELEGRAM_ADMIN_IDS", " 5000001, 5000002 ") == "5000001,5000002"


def test_first_time_values_generate_secrets_and_keep_existing() -> None:
    values = env.first_time_values(
        {"SEARCH_PROVIDER": "osm", "TELEGRAM_ADMIN_IDS": "42424242"},
        _answers("cpu_smyagent", "cpu_smy", HARD_PASSWORD, TOKEN_A, TOKEN_B),
    )
    assert values["APP_ENV"] == "production"
    assert values["APP_BASE_URL"] == "https://agent.itcode.uz"
    assert values["OUTBOUND_SENDING_ENABLED"] == "false"
    assert len(values["APP_SECRET_KEY"]) >= 32 and len(values["TELEGRAM_WEBHOOK_SECRET"]) >= 32
    assert values["TELEGRAM_ADMIN_IDS"] == "42424242"  # existing value not asked again
    again = env.first_time_values(values, _answers())  # nothing left to ask
    assert again["APP_SECRET_KEY"] == values["APP_SECRET_KEY"]  # secrets never rotated silently


def test_generated_env_is_read_correctly_by_the_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in env.parse_env(EXAMPLE):
        monkeypatch.delenv(key, raising=False)  # real env vars would win over the file
    values = env.first_time_values(
        {}, _answers("cpu_smyagent", "cpu_smy", HARD_PASSWORD, TOKEN_A, TOKEN_B, "5000001")
    )
    values["SMTP_FROM"] = "Mustafo — ITcoDe.Uz <agent@itcode.uz>"
    values["SMTP_HOST"] = "mail.itcode.uz"
    values["SMTP_PASSWORD"] = "a#b $c {x} $"
    target = tmp_path / ".env"
    env.write_private(target, env.render(EXAMPLE, values))
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    settings = load_settings(_env_file=target)
    assert settings.app_env.value == "production"
    assert settings.smtp_from == "Mustafo — ITcoDe.Uz <agent@itcode.uz>"
    assert settings.smtp_password.get_secret_value() == "a#b $c {x} $"  # no expansion/cut
    assert settings.telegram_admin_ids == [5000001]
    assert settings.telegram_admin_bot_token.get_secret_value() == TOKEN_A
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url.get_secret_value())
    assert url.password == HARD_PASSWORD and url.database == "cpu_smyagent"
    # Re-reading and rendering again is stable (idempotent).
    reparsed = env.parse_env(target.read_text(encoding="utf-8"))
    assert env.render(EXAMPLE, reparsed) == target.read_text(encoding="utf-8")


def test_render_keeps_example_order_comments_and_extra_keys() -> None:
    text = env.render(EXAMPLE, {"APP_ENV": "production", "LEGACY_KEY": "1"})
    assert text.startswith("# SMY Agent configuration")
    assert "APP_ENV=production" in text
    assert text.rstrip().endswith("LEGACY_KEY=1")
    for key in env.parse_env(EXAMPLE):
        assert f"\n{key}=" in "\n" + text  # every documented setting is present


def test_cli_set_one_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env, "TARGET", tmp_path / ".env")
    monkeypatch.setattr(env, "_ask_terminal", lambda q, d, h: "agent@itcode.uz")
    assert env.main(["--set", "smtp_username"]) == 0
    assert "SMTP_USERNAME=agent@itcode.uz" in (tmp_path / ".env").read_text()
    assert env.main(["--set", "NOT_A_SETTING"]) == 1


def test_invalid_or_empty_answer_is_asked_again(capsys: pytest.CaptureFixture[str]) -> None:
    # A bad DB name and a truncated token are asked again instead of exiting: on a phone the
    # next paste would otherwise land in bash (and its history).
    values = env.first_time_values(
        {"TELEGRAM_ADMIN_IDS": "42424242"},
        _answers(
            "bad name!", "cpu_smyagent", "cpu_smy", HARD_PASSWORD, "123:short", TOKEN_A, TOKEN_B
        ),
    )
    assert values["TELEGRAM_ADMIN_BOT_TOKEN"] == TOKEN_A
    assert values["DATABASE_URL"].endswith("/cpu_smyagent?charset=utf8mb4")
    assert "avval Paste, keyin Enter" in capsys.readouterr().out


def test_gives_up_after_three_bad_answers() -> None:
    with pytest.raises(env.SetupError):
        env.first_time_values({}, _answers("x y", "a b", "c d"))


def test_failed_run_discards_pasted_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env, "EXAMPLE", ROOT / ".env.example")
    monkeypatch.setattr(env, "TARGET", tmp_path / ".env")

    def refuse(_q: str, _d: str, _h: bool) -> str:
        raise EOFError

    flushed: list[bool] = []
    monkeypatch.setattr(env, "_ask_terminal", refuse)
    monkeypatch.setattr(env, "_discard_pending_input", lambda: flushed.append(True))
    assert env.main([]) == 1
    assert flushed == [True] and not (tmp_path / ".env").exists()
