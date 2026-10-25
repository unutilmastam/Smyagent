from __future__ import annotations

import pytest

from app.domain.contacts import (
    is_role_email,
    normalize_email,
    normalize_phone,
    normalize_telegram,
)
from app.domain.errors import DomainError


@pytest.mark.parametrize(
    ("raw", "country", "expected"),
    [
        ("90 123-45-67", "UZ", "+998901234567"),
        ("(99) 888 77 66", "uz", "+998998887766"),
        ("+998 90 123 45 67", "UZ", "+998901234567"),
        ("998901234567", "UZ", "+998901234567"),
        ("00998901234567", "KZ", "+998901234567"),  # explicit international wins
        ("8 701 234 56 78", "KZ", "+77012345678"),
        ("+7 (701) 234-56-78", "KZ", "+77012345678"),
        ("0555 123 456", "KG", "+996555123456"),
        ("93 123 4567", "TJ", "+992931234567"),
        ("+49 30 1234567", "UZ", "+49301234567"),
    ],
)
def test_normalize_phone(raw: str, country: str, expected: str) -> None:
    assert normalize_phone(raw, country) == expected


@pytest.mark.parametrize(
    ("raw", "country"),
    [("", "UZ"), ("12345", "UZ"), ("90 123 45", "UZ"), ("1234567", "RU"), ("+1", "UZ")],
)
def test_normalize_phone_rejects(raw: str, country: str) -> None:
    with pytest.raises(DomainError):
        normalize_phone(raw, country)


def test_email() -> None:
    assert normalize_email("  Info@DenovSavdo.UZ ") == "info@denovsavdo.uz"
    assert is_role_email("sales@x.uz") and not is_role_email("aziz.karimov@x.uz")
    for bad in ("nope", "a@b", "a..b@x.uz", "@x.uz"):
        with pytest.raises(DomainError):
            normalize_email(bad)


@pytest.mark.parametrize(
    "raw", ["@Denov_Savdo", "denov_savdo", "t.me/denov_savdo", "https://t.me/Denov_Savdo/"]
)
def test_telegram(raw: str) -> None:
    assert normalize_telegram(raw) == "@denov_savdo"


@pytest.mark.parametrize("raw", ["@abc", "@1denov", "@denov savdo", "https://example.com/x"])
def test_telegram_rejects(raw: str) -> None:
    with pytest.raises(DomainError):
        normalize_telegram(raw)
