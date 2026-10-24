from __future__ import annotations

import io

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
