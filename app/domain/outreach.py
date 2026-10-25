"""Outbound outreach rules (CLAUDE.md §13.2a, §15.3, M9). Pure.

Email to public business addresses only, with daily caps and warm-up, one first
message and at most one follow-up per company, an opt-out in every message, and an
automatic pause on bounces or spam complaints. Telegram and phone are owner tasks
(one tap / call manually) — never automated from personal accounts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from app.domain.persona import PERSONA, Language
from app.domain.proposals import template_language

BOUNCE_RATE_LIMIT = 0.05
MIN_SAMPLE_FOR_BOUNCE_RATE = 20


class Channel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    PHONE = "phone"


class OutreachKind(str, Enum):
    FIRST = "first"
    FOLLOW_UP = "follow_up"


class OutreachStatus(str, Enum):
    QUEUED = "QUEUED"  # email waiting for the sender job
    SENDING = "SENDING"  # handed to SMTP; if a run dies here we never resend
    SENT = "SENT"
    UNKNOWN = "UNKNOWN"  # the run died mid-send: not retried, owner checks
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"
    BLOCKED = "BLOCKED"  # suppression / pause / kill switch
    TASK = "TASK"  # Telegram / phone: the owner does it
    DONE = "DONE"  # the owner sent / called
    SKIPPED = "SKIPPED"


OPEN_TASK_STATUSES = (OutreachStatus.QUEUED, OutreachStatus.TASK)
CONTACTED_STATUSES = (OutreachStatus.SENT, OutreachStatus.DONE)


@dataclass(frozen=True)
class CapPolicy:
    daily_cap: int
    warmup_start: int
    warmup_step: int


def email_cap_today(policy: CapPolicy, first_send: date | None, today: date) -> int:
    """Warm-up: start low and grow by `warmup_step` per day up to the cap."""
    if first_send is None:
        return min(policy.daily_cap, policy.warmup_start)
    days = max(0, (today - first_send).days)
    return min(policy.daily_cap, policy.warmup_start + policy.warmup_step * days)


def should_pause(*, sent: int, bounced: int, complaints: int) -> str | None:
    """Reason to auto-pause email, or None (CLAUDE.md M9)."""
    if complaints > 0:
        return f"spam complaint received ({complaints})"
    if sent >= MIN_SAMPLE_FOR_BOUNCE_RATE and bounced / sent > BOUNCE_RATE_LIMIT:
        return f"bounce rate {bounced / sent:.0%} > {BOUNCE_RATE_LIMIT:.0%} ({bounced}/{sent})"
    return None


def follow_up_due(sent_at: datetime, now: datetime, days: int) -> bool:
    return now - sent_at >= timedelta(days=days)


# --- unsubscribe tokens -------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def unsubscribe_token(secret: str, address: str) -> str:
    """`<address-b64>.<hmac>` — verifiable without a database row, not guessable."""
    addr = address.strip().lower()
    mac = hmac.new(secret.encode(), b"unsubscribe:" + addr.encode(), hashlib.sha256).digest()
    return f"{_b64(addr.encode())}.{_b64(mac[:18])}"


def verify_unsubscribe_token(secret: str, token: str) -> str | None:
    """The address the token was issued for, or None if forged/garbled."""
    try:
        addr_part, _ = token.split(".", 1)
        address = _unb64(addr_part).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    expected = unsubscribe_token(secret, address)
    return address if hmac.compare_digest(expected, token) else None


# --- texts --------------------------------------------------------------------

L = Language
_FOLLOW_UP: dict[Language, str] = {
    L.UZ: (
        "{company} jamoasiga,\n\nBir necha kun oldin sizga yozgan edik. Agar sayt, Telegram bot "
        "yoki jarayonlarni avtomatlashtirish mavzusi qiziq bo'lsa, shu xatga qisqa javob "
        "yozing — savollaringizga javob beraman."
    ),
    L.RU: (
        "Команде {company},\n\nНесколько дней назад мы вам писали. Если тема сайта, "
        "Telegram-бота или автоматизации интересна, ответьте коротко на это письмо — "
        "отвечу на ваши вопросы."
    ),
    L.EN: (
        "Dear {company} team,\n\nWe wrote to you a few days ago. If a website, a Telegram bot "
        "or automation is of interest, just reply briefly to this email — I'm happy to answer "
        "your questions."
    ),
}
_FOLLOW_UP_SUBJECT = {
    L.UZ: "Oldingi xatimiz bo'yicha — {company}",
    L.RU: "По нашему письму — {company}",
    L.EN: "Following up — {company}",
}
_UNSUBSCRIBE = {
    L.UZ: 'Xat olishni to\'xtatish: {url} (yoki "STOP" deb javob yozing)',
    L.RU: "Отписаться: {url} (или ответьте «STOP»)",
    L.EN: 'Unsubscribe: {url} (or reply "STOP")',
}
SENDER_IDENTITY = "ITcoDe.Uz — Denov, Uzbekistan — itcode.uz"


def _lang(language: Language) -> Language:
    lang = template_language(language)
    return lang if lang in _FOLLOW_UP else Language.EN


def follow_up(company: str, language: Language) -> tuple[str, str]:
    """(subject, body) — disclosure first, opt-out and signature last."""
    lang = _lang(language)
    persona = PERSONA[lang]
    body = "\n\n".join(
        [
            persona.disclosure,
            _FOLLOW_UP[lang].replace("{company}", company),
            persona.opt_out,
            persona.signature,
        ]
    )
    return _FOLLOW_UP_SUBJECT[lang].replace("{company}", company), body


def email_footer(language: Language, unsubscribe_url: str) -> str:
    """Honest sender identification + an opt-out link in every email (§15.3)."""
    lang = _lang(language)
    return f"\n\n—\n{_UNSUBSCRIBE[lang].replace('{url}', unsubscribe_url)}\n{SENDER_IDENTITY}"
