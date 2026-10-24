"""Operator CLI, runnable from cPanel Terminal inside the app virtualenv.

python -m app.cli check-config
python -m app.cli create-owner --username bahrullo
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence

from app.application.auth import AuthService, OwnerExistsError
from app.core.config import ConfigurationError, get_settings
from app.domain.errors import DomainError
from app.infrastructure.database import Database


def _check_config() -> int:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1
    database = Database(settings.database_url.get_secret_value())
    db_ok = database.ping()
    database.dispose()
    print(f"Configuration OK (APP_ENV={settings.app_env.value}).")
    print(f"Database reachable: {'yes' if db_ok else 'NO'}")
    return 0 if db_ok else 1


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Password (min 12 chars): ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        raise DomainError("passwords do not match")
    return first


def _create_owner(username: str, password_stdin: bool) -> int:
    try:
        settings = get_settings()
        password = _read_password(password_stdin)
    except (ConfigurationError, DomainError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    database = Database(settings.database_url.get_secret_value())
    try:
        with database.transaction() as session:
            service = AuthService(session, secret_key=settings.app_secret_key.get_secret_value())
            user = service.create_owner(username, password)
            name = user.username
    except OwnerExistsError:
        print("Error: an owner account already exists. Nothing changed.", file=sys.stderr)
        return 1
    except DomainError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        database.dispose()
    print(f"Owner '{name}' created. Log in at /login.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="SMY Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-config", help="validate settings and database connectivity")
    owner = sub.add_parser("create-owner", help="create the single owner account (once)")
    owner.add_argument("--username", required=True)
    owner.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from stdin instead of prompting (for scripts)",
    )
    args = parser.parse_args(argv)
    if args.command == "check-config":
        return _check_config()
    return _create_owner(args.username, args.password_stdin)


if __name__ == "__main__":
    sys.exit(main())
