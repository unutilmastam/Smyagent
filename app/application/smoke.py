"""Post-deploy smoke test (M11): one command that says whether the live system is healthy.

    python -m app.cli smoke-test

Each check is ✓ ok, ⚠ warn (works, but something needs attention) or ✗ fail (broken).
Messages are in Uzbek for the owner; no secret is ever printed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path

import httpx
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from app.application.automation import cron_view
from app.core.config import Environment, Settings
from app.domain.automation import CronHealth
from app.infrastructure.database import Database
from app.infrastructure.database.backup import latest_backup, verify
from app.infrastructure.database.models import User
from app.infrastructure.database.types import utcnow
from app.infrastructure.telegram.client import TelegramClient, TelegramError

ROOT = Path(__file__).resolve().parents[2]
BACKUP_MAX_AGE = timedelta(hours=36)
OWNER_WEBHOOK = "/api/v1/telegram/webhook"
CLIENT_WEBHOOK = "/api/v1/telegram/client-webhook"


class Level(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


ICONS = {Level.OK: "✓", Level.WARN: "⚠", Level.FAIL: "✗"}


@dataclass(frozen=True)
class Check:
    name: str
    level: Level
    message: str

    def line(self) -> str:
        return f"{ICONS[self.level]} {self.name}: {self.message}"


WebhookInfo = Callable[[str], dict[str, object]]


def _telegram_info(token: str) -> dict[str, object]:
    return TelegramClient(token).webhook_info()


@dataclass
class SmokeTest:
    settings: Settings
    database: Database
    backup_dir: Path
    http: httpx.Client | None = None
    webhook_info: WebhookInfo = _telegram_info
    check_http: bool = True

    def run(self) -> list[Check]:
        checks = [self._config()]
        db = self._database()
        checks.append(db)
        if db.level is not Level.FAIL:
            checks += [self._migrations(), self._owner(), self._cron()]
        if self.check_http:
            checks.append(self._http())
        checks += self._webhooks()
        checks.append(self._email())
        checks.append(self._backup())
        return checks

    # -- checks ------------------------------------------------------------------

    def _config(self) -> Check:
        s = self.settings
        if s.app_env is not Environment.PRODUCTION:
            return Check("Sozlamalar", Level.WARN, f"APP_ENV={s.app_env.value} (production emas)")
        sending = "yoqilgan" if s.outbound_sending_enabled else "o'chiq"
        return Check("Sozlamalar", Level.OK, f"production, tashqi yuborish {sending}")

    def _database(self) -> Check:
        if self.database.ping():
            return Check("Baza", Level.OK, "ulanish bor")
        return Check("Baza", Level.FAIL, "ulanib bo'lmadi — .env dagi DATABASE_URL ni tekshiring")

    def _migrations(self) -> Check:
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        head = script.get_current_head()
        with self.database.engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        if current == head:
            return Check("Migratsiya", Level.OK, f"oxirgi versiya ({head})")
        return Check(
            "Migratsiya", Level.FAIL, f"baza {current}, kod {head} — bash scripts/deploy.sh"
        )

    def _owner(self) -> Check:
        with self.database.transaction() as session:
            owners = session.scalar(select(func.count()).select_from(User)) or 0
        if owners:
            return Check("Akkaunt", Level.OK, "egasi bor")
        return Check("Akkaunt", Level.FAIL, "egasi yo'q — python -m app.cli create-owner")

    def _cron(self) -> Check:
        with self.database.transaction() as session:
            cron = cron_view(session)
        if cron.health is CronHealth.OK:
            return Check("Cron", Level.OK, f"oxirgi ishga tushish {cron.minutes_ago} daqiqa oldin")
        if cron.health is CronHealth.NEVER:
            return Check("Cron", Level.WARN, "hali ishga tushmagan — cPanel → Cron Jobs")
        return Check("Cron", Level.WARN, f"{cron.minutes_ago} daqiqadan beri ishlamayapti")

    def _http(self) -> Check:
        base = self.settings.app_base_url.rstrip("/")
        client = self.http or httpx.Client(timeout=20, follow_redirects=False)
        try:
            for path in ("/api/v1/health", "/api/v1/ready"):
                response = client.get(base + path)
                if response.status_code != 200:
                    return Check("Sayt", Level.FAIL, f"{path} → HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            return Check("Sayt", Level.FAIL, f"{base} ochilmadi ({type(exc).__name__})")
        finally:
            if self.http is None:
                client.close()
        return Check("Sayt", Level.OK, f"{base} javob beryapti")

    def _webhooks(self) -> list[Check]:
        base = self.settings.app_base_url.rstrip("/")
        bots = (
            ("Direktor boti", self.settings.telegram_admin_bot_token, OWNER_WEBHOOK),
            ("Mustafo boti", self.settings.telegram_client_bot_token, CLIENT_WEBHOOK),
        )
        checks = []
        for name, token, path in bots:
            secret = token.get_secret_value()
            if not secret:
                checks.append(Check(name, Level.WARN, "token yo'q — bot o'chiq"))
                continue
            try:
                info = self.webhook_info(secret)
            except TelegramError as exc:
                checks.append(Check(name, Level.FAIL, f"Telegram: {exc}"))
                continue
            if info.get("url") != base + path:
                checks.append(
                    Check(name, Level.FAIL, "webhook boshqa manzilda — telegram-set-…-webhook")
                )
            elif info.get("last_error_message"):
                checks.append(Check(name, Level.WARN, f"oxirgi xato: {info['last_error_message']}"))
            else:
                checks.append(Check(name, Level.OK, "webhook to'g'ri, xato yo'q"))
        return checks

    def _email(self) -> Check:
        s = self.settings
        if not s.email_enabled:
            return Check("Email", Level.WARN, "ulanmagan — docs/email-uz.md")
        reading = "javoblar o'qiladi" if s.imap_host else "IMAP yo'q — javoblar o'qilmaydi"
        if not s.outbound_sending_enabled:
            return Check("Email", Level.OK, f"sozlangan, yuborish o'chiq; {reading}")
        level = Level.OK if s.imap_host else Level.WARN
        return Check("Email", level, f"sozlangan, yuborish YOQILGAN; {reading}")

    def _backup(self) -> Check:
        latest = latest_backup(self.backup_dir) if self.backup_dir.is_dir() else None
        if latest is None:
            return Check("Zaxira", Level.WARN, f"{self.backup_dir} da zaxira yo'q")
        age = utcnow().timestamp() - latest.stat().st_mtime
        result = verify(latest)
        if not result.ok:
            return Check("Zaxira", Level.FAIL, f"{latest.name} buzilgan: {result.problem}")
        hours = int(age // 3600)
        if age > BACKUP_MAX_AGE.total_seconds():
            return Check(
                "Zaxira", Level.WARN, f"oxirgisi {hours} soat oldin — backup cron'ini tekshiring"
            )
        return Check(
            "Zaxira", Level.OK, f"{latest.name}: {len(result.tables)} jadval, {hours} soat oldin"
        )


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.level is Level.FAIL for c in checks) else 0
