"""Operator CLI, runnable from cPanel Terminal inside the app virtualenv.

python -m app.cli check-config
python -m app.cli create-owner --username bahrullo
python -m app.cli telegram-set-webhook
python -m app.cli telegram-webhook-info
python -m app.cli telegram-set-client-webhook
python -m app.cli db-backup [--dir ~/smyagent_data/backups] [--keep 14]
python -m app.cli db-backup-verify [--file PATH]
python -m app.cli db-restore-drill --target-database itcode_smyrestore
python -m app.cli smoke-test [--no-http]
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
CLIENT_WEBHOOK_PATH = "/api/v1/telegram/client-webhook"


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


def _telegram_set_client_webhook() -> int:
    settings = get_settings()
    token = settings.telegram_client_bot_token.get_secret_value()
    secret = settings.telegram_webhook_secret.get_secret_value()
    if not token or not secret:
        print(
            "Error: set TELEGRAM_CLIENT_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first.",
            file=sys.stderr,
        )
        return 1
    base_url = settings.app_base_url.rstrip("/")
    if not base_url.startswith("https://"):
        print("Error: APP_BASE_URL must be https:// for Telegram webhooks.", file=sys.stderr)
        return 1
    try:
        TelegramClient(token).set_webhook(base_url + CLIENT_WEBHOOK_PATH, secret_token=secret)
    except TelegramError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Client bot webhook set to {base_url}{CLIENT_WEBHOOK_PATH}")
    return 0


def _db_backup(directory: str, keep: int) -> int:
    from pathlib import Path

    from app.infrastructure.database.backup import BackupError, backup

    try:
        settings = get_settings()
        path = backup(
            settings.database_url.get_secret_value(), Path(directory).expanduser(), keep=keep
        )
    except (ConfigurationError, BackupError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if path is None:
        print("Nothing to back up yet (no tables).")
    else:
        print(f"Backup written: {path}")
    return 0


def _backup_verify(directory: str, file: str | None) -> int:
    from pathlib import Path

    from app.infrastructure.database.backup import latest_backup, verify

    path = Path(file).expanduser() if file else latest_backup(Path(directory).expanduser())
    if path is None or not path.exists():
        print("Zaxira fayli topilmadi.", file=sys.stderr)
        return 1
    result = verify(path)
    size_kb = result.size_bytes // 1024
    if result.ok:
        print(
            f"✓ {path.name}: {len(result.tables)} jadval, "
            f"{result.insert_statements} INSERT, {size_kb} KB — butun"
        )
        return 0
    print(f"✗ {path.name}: {result.problem}", file=sys.stderr)
    return 1


def _restore_drill(directory: str, file: str | None, target: str, keep: bool) -> int:
    from pathlib import Path

    from app.infrastructure.database.backup import latest_backup, restore_drill

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1
    path = Path(file).expanduser() if file else latest_backup(Path(directory).expanduser())
    if path is None or not path.exists():
        print("Zaxira fayli topilmadi.", file=sys.stderr)
        return 1
    print(f"Tiklash mashqi: {path.name} → {target} (asosiy bazaga tegilmaydi)")
    result = restore_drill(settings.database_url.get_secret_value(), path, target, keep=keep)
    if not result.ok:
        print(f"✗ {result.problem}", file=sys.stderr)
        return 1
    print(f"✓ {result.tables} jadval tiklandi, jami {sum(result.rows.values())} qator.")
    for name, (restored, live) in sorted(result.differences.items()):
        print(f"  ~ {name}: zaxirada {restored}, hozir {live} (zaxiradan keyin o'zgargan)")
    print("✓ Mashq tugadi." + ("" if keep else f" {target} yana bo'shatildi."))
    return 0


def _smoke_test(directory: str, check_http: bool) -> int:
    from pathlib import Path

    from app.application.smoke import SmokeTest, exit_code

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(f"✗ Sozlamalar: {exc}", file=sys.stderr)
        return 1
    database = Database(settings.database_url.get_secret_value())
    try:
        checks = SmokeTest(
            settings, database, Path(directory).expanduser(), check_http=check_http
        ).run()
    finally:
        database.dispose()
    for check in checks:
        print(check.line())
    code = exit_code(checks)
    print("\n" + ("✅ Hammasi joyida." if code == 0 else "❌ Yuqoridagi ✗ larni tuzating."))
    return code


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
    sub.add_parser("telegram-set-client-webhook", help="register the Mustafo client bot webhook")
    backup_parser = sub.add_parser("db-backup", help="gzip'd database dump outside the web root")
    backup_parser.add_argument("--dir", default="~/smyagent_data/backups")
    backup_parser.add_argument("--keep", type=int, default=14)
    verify_parser = sub.add_parser("db-backup-verify", help="check that a backup is complete")
    verify_parser.add_argument("--dir", default="~/smyagent_data/backups")
    verify_parser.add_argument("--file", help="a backup file (default: the newest)")
    drill = sub.add_parser(
        "db-restore-drill", help="restore a backup into an empty scratch database and compare"
    )
    drill.add_argument(
        "--target-database", required=True, help="an EMPTY database, not the live one"
    )
    drill.add_argument("--dir", default="~/smyagent_data/backups")
    drill.add_argument("--file", help="a backup file (default: the newest)")
    drill.add_argument("--keep", action="store_true", help="keep the restored copy")
    smoke = sub.add_parser("smoke-test", help="post-deploy health check of the live system")
    smoke.add_argument("--dir", default="~/smyagent_data/backups")
    smoke.add_argument("--no-http", action="store_true", help="skip the HTTPS health check")
    args = parser.parse_args(argv)
    if args.command == "db-backup-verify":
        return _backup_verify(args.dir, args.file)
    if args.command == "db-restore-drill":
        return _restore_drill(args.dir, args.file, args.target_database, args.keep)
    if args.command == "smoke-test":
        return _smoke_test(args.dir, not args.no_http)
    if args.command == "check-config":
        return _check_config()
    if args.command == "telegram-set-webhook":
        return _telegram_set_webhook()
    if args.command == "db-backup":
        return _db_backup(args.dir, max(1, args.keep))
    if args.command == "telegram-set-client-webhook":
        return _telegram_set_client_webhook()
    if args.command == "telegram-webhook-info":
        return _telegram_webhook_info()
    return _create_owner(args.username, args.password_stdin)


if __name__ == "__main__":
    sys.exit(main())
