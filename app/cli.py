"""Operator CLI, runnable from cPanel Terminal inside the app virtualenv.

python -m app.cli check-config
python -m app.cli create-owner --username bahrullo
python -m app.cli telegram-set-webhook
python -m app.cli telegram-webhook-info
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
from app.infrastructure.telegram.client import TelegramClient, TelegramError

WEBHOOK_PATH = "/api/v1/telegram/webhook"


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


def _telegram_client() -> tuple[TelegramClient, str] | None:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return None
    if not settings.owner_bot_enabled:
        print(
            "Error: set TELEGRAM_ADMIN_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET and "
            "TELEGRAM_ADMIN_IDS first.",
            file=sys.stderr,
        )
        return None
    client = TelegramClient(settings.telegram_admin_bot_token.get_secret_value())
    return client, settings.app_base_url.rstrip("/")


def _telegram_set_webhook() -> int:
    prepared = _telegram_client()
    if prepared is None:
        return 1
    client, base_url = prepared
    if not base_url.startswith("https://"):
        print("Error: APP_BASE_URL must be https:// for Telegram webhooks.", file=sys.stderr)
        return 1
    secret = get_settings().telegram_webhook_secret.get_secret_value()
    try:
        client.set_webhook(base_url + WEBHOOK_PATH, secret_token=secret)
    except TelegramError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Webhook set to {base_url}{WEBHOOK_PATH}")
    return 0


def _telegram_webhook_info() -> int:
    prepared = _telegram_client()
    if prepared is None:
        return 1
    client, _ = prepared
    try:
        info = client.webhook_info()
    except TelegramError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for key in ("url", "pending_update_count", "last_error_date", "last_error_message"):
        print(f"{key}: {info.get(key, '')}")
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
    sub.add_parser("telegram-set-webhook", help="register the owner bot webhook with Telegram")
    sub.add_parser("telegram-webhook-info", help="show Telegram's view of the webhook")
    args = parser.parse_args(argv)
    if args.command == "check-config":
        return _check_config()
    if args.command == "telegram-set-webhook":
        return _telegram_set_webhook()
    if args.command == "telegram-webhook-info":
        return _telegram_webhook_info()
    return _create_owner(args.username, args.password_stdin)


if __name__ == "__main__":
    sys.exit(main())
