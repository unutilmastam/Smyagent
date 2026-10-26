"""Create or update the server `.env` interactively (owner, cPanel Terminal, phone).

Usage (from the app folder, with the app's virtualenv Python):
    python scripts/setup_env.py              # first time: asks everything needed to start
    python scripts/setup_env.py --set SMTP_PASSWORD   # (re)enter one value later

Why a file: variables typed in "Setup Python App" reach only the web app, not
Terminal commands or cron jobs. One `.env` in the app folder (mode 600, ignored
by Git) is read by all three. Secrets are typed hidden and never printed.
Standard library only, so it runs before `pip install`.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"
DEFAULT_BASE_URL = "https://agent.itcode.uz"

_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
_TOKEN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
_IDS = re.compile(r"^\d{4,}(,\d{4,})*$")
_DB_NAME = re.compile(r"^[A-Za-z0-9_]{1,64}$")
ATTEMPTS = 3
_PLAIN = re.compile(r"^[A-Za-z0-9_./:@%+,=-]*$")

# Keys that are secret: typed hidden, never echoed.
SECRET_KEYS = {
    "APP_SECRET_KEY",
    "DATABASE_URL",
    "AI_API_KEY",
    "SEARCH_API_KEY",
    "TELEGRAM_ADMIN_BOT_TOKEN",
    "TELEGRAM_CLIENT_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "SMTP_PASSWORD",
    "IMAP_PASSWORD",
}
# Fixed production values written on first setup (owner can change them later).
FIRST_TIME_FIXED = {
    "APP_ENV": "production",
    "APP_BASE_URL": DEFAULT_BASE_URL,
    "OUTBOUND_SENDING_ENABLED": "false",
    "SEARCH_PROVIDER": "osm",
    "DEFAULT_TIMEZONE": "Asia/Tashkent",
}


class SetupError(ValueError):
    pass


def database_url(name: str, user: str, password: str, host: str = "localhost") -> str:
    """mysql+pymysql URL; user and password are percent-encoded (e.g. '@', '#', '/')."""
    if not _DB_NAME.match(name) or not _DB_NAME.match(user):
        raise SetupError("baza nomi va foydalanuvchi faqat harf, raqam va _ dan iborat bo'ladi")
    if not password:
        raise SetupError("parol bo'sh bo'lmasin")
    return (
        f"mysql+pymysql://{quote(user, safe='')}:{quote(password, safe='')}@{host}/"
        f"{name}?charset=utf8mb4"
    )


BOOL_KEYS = {"OUTBOUND_SENDING_ENABLED", "SMTP_USE_SSL"}
INT_KEYS = {"SMTP_PORT", "IMAP_PORT", "DAILY_SEARCH_LIMIT"}
DECIMAL_KEYS = {"MONTHLY_AI_BUDGET_USD", "DAILY_AI_BUDGET_USD"}
_TRUE = {"true", "ha", "yes", "1", "on"}
_FALSE = {"false", "yoq", "yo'q", "no", "0", "off"}


def _typed(key: str, value: str) -> str | None:
    """Normalized value for typed settings, so a typo never reaches .env (and the app)."""
    lowered = value.lower()
    if key in BOOL_KEYS:
        if lowered in _TRUE:
            return "true"
        if lowered in _FALSE:
            return "false"
        raise SetupError("faqat true yoki false deb yozing")
    if key in INT_KEYS:
        if not value.isdigit():
            raise SetupError("faqat butun son yozing (masalan 465)")
        return str(int(value))
    if key in DECIMAL_KEYS:
        if not re.fullmatch(r"\d+(\.\d{1,4})?", value):
            raise SetupError("son yozing, masalan 10 yoki 0.5")
        return value
    return None


def validate(key: str, value: str) -> str:
    value = value.strip()
    typed = _typed(key, value)
    if typed is not None:
        return typed
    bot_token = key in ("TELEGRAM_ADMIN_BOT_TOKEN", "TELEGRAM_CLIENT_BOT_TOKEN")
    if bot_token and value and not _TOKEN.match(value):
        raise SetupError("token shunday ko'rinishda bo'ladi: 123456789:AA... (BotFather)")
    if key == "TELEGRAM_ADMIN_IDS" and value and not _IDS.match(value.replace(" ", "")):
        raise SetupError("faqat raqamli ID (masalan 123456789), bir nechta bo'lsa vergul bilan")
    if key == "APP_BASE_URL" and not value.startswith("https://"):
        raise SetupError("manzil https:// bilan boshlanishi kerak")
    if "\n" in value or "\r" in value:
        raise SetupError("qiymat bir qatorda bo'lishi kerak")
    if "'" in value:
        raise SetupError("qiymatda ' (apostrof) belgisi bo'lmasin")
    if "${" in value:
        # The .env reader expands ${NAME} even inside quotes: the value would change.
        raise SetupError("qiymatda ${ ketma-ketligi bo'lmasin (boshqa parol tanlang)")
    return value.replace(" ", "") if key == "TELEGRAM_ADMIN_IDS" else value


def format_value(value: str) -> str:
    """Single quotes for anything not plain: no `$` expansion, no `#` comment cut-off."""
    return value if _PLAIN.match(value) else f"'{value}'"


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    return raw


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = _LINE.match(line.strip())
        if match:
            values[match.group(1)] = _unquote(match.group(2))
    return values


def render(example: str, values: dict[str, str]) -> str:
    """Keep the example's order and comments; fill in values; keep extra keys at the end."""
    out: list[str] = []
    seen: set[str] = set()
    for line in example.splitlines():
        match = _LINE.match(line.strip())
        if match:
            key = match.group(1)
            seen.add(key)
            out.append(f"{key}={format_value(values.get(key, _unquote(match.group(2))))}")
        else:
            out.append(line)
    extra = [k for k in values if k not in seen]
    if extra:
        out += ["", "# Extra keys kept from the previous .env"]
        out += [f"{k}={format_value(values[k])}" for k in extra]
    return "\n".join(out) + "\n"


def write_private(path: Path, text: str) -> None:
    """Atomic write with mode 600 (only the cPanel user can read it)."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def first_time_values(
    current: dict[str, str], ask: Callable[[str, str, bool], str]
) -> dict[str, str]:
    """Values for a first start; existing non-empty values are kept, not asked again."""
    values = dict(current)
    for key, fixed in FIRST_TIME_FIXED.items():
        values.setdefault(key, fixed)
        if not values[key]:
            values[key] = fixed
    for key in ("APP_SECRET_KEY", "TELEGRAM_WEBHOOK_SECRET"):
        if len(values.get(key, "")) < 32:
            values[key] = secrets.token_urlsafe(36)  # generated, never shown
    if not values.get("DATABASE_URL", "").startswith("mysql"):
        name = ask_valid(
            ask,
            "MySQL baza nomi (cPanel → MySQL Databases, masalan cpuser_smyagent)",
            False,
            _check_db_name,
        )
        user = ask_valid(
            ask, "MySQL foydalanuvchi nomi (masalan cpuser_smy)", False, _check_db_name
        )
        password = ask_valid(ask, "MySQL foydalanuvchi paroli", True, lambda v: v)
        values["DATABASE_URL"] = database_url(name, user, password)
    prompts = (
        ("TELEGRAM_ADMIN_BOT_TOKEN", "@direktorsmybot tokeni (BotFather)", True),
        ("TELEGRAM_CLIENT_BOT_TOKEN", "@mustafosmybot tokeni (BotFather)", True),
        ("TELEGRAM_ADMIN_IDS", "Sizning raqamli Telegram ID (@userinfobot)", False),
    )
    for key, question, hidden in prompts:
        if not values.get(key):
            values[key] = ask_valid(ask, question, hidden, partial(validate, key))
    return values


def _check_db_name(value: str) -> str:
    value = value.strip()
    if not _DB_NAME.match(value):
        raise SetupError("faqat harf, raqam va _ (masalan cpuser_smyagent)")
    return value


def ask_valid(
    ask: Callable[[str, str, bool], str],
    question: str,
    hidden: bool,
    check: Callable[[str], str],
    attempts: int = ATTEMPTS,
    default: str = "",
) -> str:
    """Ask again (up to `attempts` times) on an empty or invalid answer instead of exiting.

    Exiting early is dangerous on a phone: the token pasted next would land in bash and be
    saved in the shell history.
    """
    last = ""
    for _ in range(attempts):
        try:
            return check(ask(question, default, hidden))
        except SetupError as exc:
            last = str(exc)
            print(f"  ✗ {last}. Qayta kiriting (avval Paste, keyin Enter).")
    raise SetupError(f"{question}: {last}")


EMAIL_HOST = "mail.itcode.uz"
EMAIL_ADDRESS = "agent@itcode.uz"
SENDER_NAME = "Mustafo — ITcoDe.Uz"
_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_ADDRESS = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def _check_host(value: str) -> str:
    value = value.strip().lower()
    if not _HOST.match(value):
        raise SetupError("server nomi masalan mail.itcode.uz ko'rinishida bo'ladi")
    return value


def _check_address(value: str) -> str:
    value = value.strip().lower()
    if not _ADDRESS.match(value):
        raise SetupError("email manzil masalan agent@itcode.uz ko'rinishida bo'ladi")
    return value


def email_values(current: dict[str, str], ask: Callable[[str, str, bool], str]) -> dict[str, str]:
    """One mailbox for sending (SMTP 465/SSL) and reading replies (IMAP 993).

    OUTBOUND_SENDING_ENABLED is not touched: the owner turns sending on separately,
    after the test email (docs/email-uz.md).
    """
    values = dict(current)
    host = ask_valid(
        ask,
        "Pochta serveri (Connect Devices → Outgoing Server)",
        False,
        _check_host,
        default=EMAIL_HOST,
    )
    address = ask_valid(ask, "Pochta manzili", False, _check_address, default=EMAIL_ADDRESS)
    password = ask_valid(
        ask,
        f"{address} paroli (Email Accounts'da qo'ygan)",
        True,
        partial(validate, "SMTP_PASSWORD"),
    )
    values.update(
        {
            "SMTP_HOST": host,
            "SMTP_PORT": "465",
            "SMTP_USE_SSL": "true",
            "SMTP_USERNAME": address,
            "SMTP_PASSWORD": password,
            "SMTP_FROM": f"{SENDER_NAME} <{address}>",
            "IMAP_HOST": host,
            "IMAP_PORT": "993",
            "IMAP_USERNAME": address,
            "IMAP_PASSWORD": password,
        }
    )
    return values


def _ask_terminal(question: str, default: str, hidden: bool) -> str:
    prompt = f"{question}{f' [{default}]' if default else ''}: "
    for _ in range(ATTEMPTS):
        answer = getpass.getpass(prompt) if hidden else input(prompt)
        answer = answer.strip() or default
        if answer:
            return answer
        print("  Bo'sh bo'lmasin — avval Paste qiling, keyin Enter.")
    raise SetupError(f"{question}: qiymat kiritilmadi")


def _discard_pending_input() -> None:
    """Drop typed-ahead/pasted text so it is not run by bash after we exit."""
    try:
        import termios

        if sys.stdin.isatty():
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (ImportError, OSError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/setup_env.py")
    parser.add_argument(
        "--set", metavar="KEY", help="enter or replace one value (e.g. SMTP_PASSWORD)"
    )
    parser.add_argument(
        "--database", action="store_true", help="re-enter MySQL name, user and password"
    )
    parser.add_argument(
        "--email", action="store_true", help="mailbox for outreach (SMTP + IMAP, one password)"
    )
    args = parser.parse_args(argv)
    if not EXAMPLE.exists():
        print("Xato: .env.example topilmadi — buyruqni ilova papkasida bajaring.", file=sys.stderr)
        return 1
    example = EXAMPLE.read_text(encoding="utf-8")
    current = parse_env(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {}
    known = parse_env(example)
    try:
        if args.set:
            key = args.set.strip().upper()
            if key not in known and key not in current:
                print(f"Xato: {key} degan sozlama yo'q (.env.example ga qarang).", file=sys.stderr)
                return 1
            hidden = key in SECRET_KEYS
            default = "" if hidden else current.get(key, "")
            value = ask_valid(
                lambda q, _d, h: _ask_terminal(q, default, h),
                f"{key} qiymati",
                hidden,
                lambda v: validate(key, v),
            )
            current[key] = value
            values = current
        elif args.email:
            values = email_values(current, _ask_terminal)
        else:
            if args.database:
                current.pop("DATABASE_URL", None)
            values = first_time_values(current, _ask_terminal)
    except (SetupError, EOFError, KeyboardInterrupt) as exc:
        _discard_pending_input()
        print(f"\nXato: {exc}. Hech narsa o'zgarmadi.", file=sys.stderr)
        return 1
    write_private(TARGET, render(example, values))
    print(f"✓ {TARGET.name} saqlandi (faqat siz o'qiy olasiz, Git'ga tushmaydi).")
    missing = [
        k
        for k in ("DATABASE_URL", "TELEGRAM_ADMIN_BOT_TOKEN", "TELEGRAM_ADMIN_IDS")
        if not values.get(k)
    ]
    if missing:
        print("Hali bo'sh: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
