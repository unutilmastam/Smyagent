"""Post-deploy smoke test (M11) with fake HTTP and Telegram."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.application.auth import AuthService
from app.application.smoke import Level, SmokeTest, exit_code
from app.core.config import load_settings
from app.infrastructure.database import Database
from app.infrastructure.database.backup import backup

BASE = "https://agent.itcode.uz"


def _settings(**kw: Any) -> Any:
    return load_settings(
        _env_file=None,
        app_env="test",
        app_base_url=BASE,
        telegram_admin_bot_token="1234567890:AAH" + "x" * 32,
        telegram_webhook_secret="w" * 40,
        telegram_admin_ids="42424242",
        **kw,
    )


def _http(status: int = 200) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json={})))


def _by_name(checks: list[Any]) -> dict[str, Any]:
    return {c.name: c for c in checks}


def test_healthy_system(db: Database, database_url: str, tmp_path: Path) -> None:
    with db.transaction() as s:
        AuthService(s, secret_key="x").create_owner("bahrullo", "Denov-ITcoDe-2026!")
    backup(database_url, tmp_path)
    smoke = SmokeTest(
        _settings(),
        db,
        tmp_path,
        http=_http(),
        webhook_info=lambda _t: {"url": BASE + "/api/v1/telegram/webhook"},
    )
    checks = _by_name(smoke.run())
    assert checks["Baza"].level is Level.OK and checks["Migratsiya"].level is Level.OK
    assert checks["Akkaunt"].level is Level.OK and checks["Sayt"].level is Level.OK
    assert checks["Direktor boti"].level is Level.OK
    assert checks["Mustafo boti"].level is Level.WARN  # no client token configured
    assert checks["Cron"].level is Level.WARN  # never ran in this test DB
    if database_url.startswith("sqlite"):
        assert checks["Zaxira"].level is Level.OK
    assert exit_code(list(checks.values())) == 0


def test_failures_are_reported(db: Database, tmp_path: Path) -> None:
    smoke = SmokeTest(
        _settings(),
        db,
        tmp_path / "none",
        http=_http(503),
        webhook_info=lambda _t: {"url": "https://elsewhere/x", "last_error_message": ""},
    )
    checks = _by_name(smoke.run())
    assert checks["Akkaunt"].level is Level.FAIL
    assert checks["Sayt"].level is Level.FAIL and "503" in checks["Sayt"].message
    assert checks["Direktor boti"].level is Level.FAIL
    assert checks["Zaxira"].level is Level.WARN
    assert exit_code(list(checks.values())) == 1
    # Nothing secret in any line.
    assert all("AAH" not in c.line() and "www" not in c.line() for c in checks.values())
