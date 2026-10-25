"""Quality Gate: no prices/commitments to clients, persona rules, evidence (M7)."""

from __future__ import annotations

import pytest

from app.domain.persona import PERSONA, Language
from app.domain.quality_gate import Verdict, cyrillic_ratio, review


def _wrap(text: str, lang: Language = Language.UZ) -> str:
    p = PERSONA[lang]
    return f"{p.disclosure}\n\n{text}\n\n{p.opt_out}\n\n{p.signature}"


CLEAN_UZ = "Sizga Telegram bot foydali bo'lishi mumkin."


def test_clean_text_is_approved() -> None:
    assert review(_wrap(CLEAN_UZ), language=Language.UZ, evidence_count=1).verdict is (
        Verdict.APPROVED
    )


@pytest.mark.parametrize(
    "text",
    [
        "Narxi 500 000 so'm.",
        "Sayt 3 mln so'mdan.",
        "Bor-yo'g'i 200$.",
        "$150 dan boshlab.",
        "UZS 900000",
        "Стоимость 1 200 000 сум.",
        "Всего 300 долларов.",
        "Цена: 5000",
        "50 000 тенге",
        "Only 99 USD.",
        "Price from 300",
        "10% chegirma!",
        "Скидка для вас.",
        "We will do it for free.",
        "Bepul maslahat beramiz.",
    ],
)
def test_prices_amounts_and_discounts_are_blocked(text: str) -> None:
    result = review(_wrap(text), language=Language.UZ, evidence_count=1)
    assert result.verdict is Verdict.REJECTED and "price" in result.codes


@pytest.mark.parametrize(
    "text",
    [
        "Natijaga kafolat beramiz.",
        "5 kun ichida tayyor qilamiz.",
        "Shartnoma tuzamiz.",
        "Гарантируем результат.",
        "Сделаем за 7 дней.",
        "We deliver within 3 days.",
        "50% oldindan to'lov.",
    ],
)
def test_commitments_are_blocked(text: str) -> None:
    result = review(_wrap(text), language=Language.UZ, evidence_count=1)
    assert result.verdict is Verdict.REJECTED and "commitment" in result.codes


@pytest.mark.parametrize(
    "text", ["Biz eng yaxshi jamoamiz.", "Mijozlarimiz mamnun.", "Sotuv 3 marta oshadi."]
)
def test_unsupported_claims_need_review(text: str) -> None:
    result = review(_wrap(text), language=Language.UZ, evidence_count=1)
    assert "unsupported_claim" in result.codes
    assert result.verdict in (Verdict.NEEDS_REVIEW, Verdict.REJECTED)


def test_phone_numbers_and_ordinary_words_are_not_prices() -> None:
    text = _wrap("Telefon: +998 90 123 45 67. Feel free to reply. Summa — so'zi emas.")
    result = review(text, language=Language.UZ, evidence_count=1)
    assert "price" not in result.codes


def test_missing_disclosure_opt_out_evidence() -> None:
    result = review(CLEAN_UZ, language=Language.UZ, evidence_count=0)
    assert result.verdict is Verdict.REJECTED
    assert {"missing_disclosure", "missing_opt_out", "no_evidence"} <= set(result.codes)


def test_empty_text_rejected() -> None:
    assert review("  ", language=Language.UZ, evidence_count=1).codes == ["empty"]


def test_language_mismatch_needs_review() -> None:
    ru_text = _wrap("Вам может пригодиться Telegram-бот.", Language.RU)
    assert review(ru_text, language=Language.RU, evidence_count=1).verdict is Verdict.APPROVED
    mismatch = review(ru_text, language=Language.EN, evidence_count=1)
    assert mismatch.verdict is Verdict.NEEDS_REVIEW and "language_mismatch" in mismatch.codes
    assert cyrillic_ratio("abc") == 0 and cyrillic_ratio("абв") == 1


def test_too_long_needs_review() -> None:
    result = review(_wrap(CLEAN_UZ + " a" * 3000), language=Language.UZ, evidence_count=1)
    assert result.verdict is Verdict.NEEDS_REVIEW and "too_long" in result.codes
