"""Public business contact normalization (CLAUDE.md §8.1 Discovery, §15.3).

Only business contacts are stored (company phones, info@/sales@ addresses, public
Telegram channels/accounts of the business) — never private individuals' data.
"""

from __future__ import annotations

import re
from enum import Enum

from app.domain.errors import DomainError


class ContactKind(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    TELEGRAM = "telegram"


# Country calling code and national significant number length (without trunk prefix).
_PHONE_PLANS: dict[str, tuple[str, int]] = {
    "UZ": ("998", 9),
    "KZ": ("7", 10),
    "KG": ("996", 9),
    "TJ": ("992", 9),
}
_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str, country: str) -> str:
    """E.164 for UZ/KZ/KG/TJ numbers, e.g. '90 123-45-67' (UZ) -> '+998901234567'.

    Numbers with an explicit international prefix ('+' or '00') keep their own country.
    """
    text = raw.strip()
    if not text:
        raise DomainError("phone is empty")
    international = text.startswith(("+", "00"))
    digits = _DIGITS.sub("", text)
    if text.startswith("00"):
        digits = digits[2:]

    if international:
        for code, length in _PHONE_PLANS.values():
            if digits.startswith(code) and len(digits) == len(code) + length:
                return "+" + digits
        if 8 <= len(digits) <= 15:
            return "+" + digits  # other countries: keep as given, length-checked
        raise DomainError("phone number has an invalid length")

    plan = _PHONE_PLANS.get(country.upper())
    if plan is None:
        raise DomainError("national phone format is only known for UZ, KZ, KG, TJ; use +<code>")
    code, length = plan
    if digits.startswith(code) and len(digits) == len(code) + length:
        return "+" + digits
    if country.upper() == "KZ" and digits.startswith("8") and len(digits) == length + 1:
        digits = digits[1:]  # Kazakh trunk prefix 8
    elif digits.startswith("0") and len(digits) == length + 1:
        digits = digits[1:]  # trunk prefix 0
    if len(digits) != length:
        raise DomainError(f"a {country.upper()} phone number needs {length} digits")
    return f"+{code}{digits}"


_EMAIL = re.compile(r"^[a-z0-9._%+-]{1,64}@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,24}$")
# Addresses that obviously belong to a business function, not a person.
ROLE_LOCAL_PARTS = frozenset(
    {
        "info",
        "sales",
        "contact",
        "contacts",
        "office",
        "hello",
        "support",
        "admin",
        "marketing",
        "order",
        "orders",
        "zakaz",
        "reception",
        "mail",
        "biz",
        "business",
    }
)


def normalize_email(raw: str) -> str:
    value = raw.strip().lower()
    if not _EMAIL.match(value) or ".." in value:
        raise DomainError("email address is not valid")
    return value


def is_role_email(email: str) -> bool:
    return email.split("@", 1)[0] in ROLE_LOCAL_PARTS


_TG = re.compile(r"^[a-z][a-z0-9_]{4,31}$")


def normalize_telegram(raw: str) -> str:
    """'@Denov_Savdo', 't.me/denov_savdo', 'https://t.me/denov_savdo' -> '@denov_savdo'."""
    value = raw.strip()
    value = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", value, flags=re.I)
    value = value.lstrip("@").split("?")[0].strip("/").lower()
    if not _TG.match(value):
        raise DomainError("Telegram username must be 5-32 chars: letters, digits, '_'")
    return "@" + value


def normalize_contact(kind: ContactKind, raw: str, *, country: str) -> str:
    if kind is ContactKind.PHONE:
        return normalize_phone(raw, country)
    if kind is ContactKind.EMAIL:
        return normalize_email(raw)
    return normalize_telegram(raw)
