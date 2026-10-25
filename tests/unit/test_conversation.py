"""Mustafo conversation rules: language, intents, disclosure, no prices (M8, CLAUDE.md §5.3)."""

from __future__ import annotations

import re

import pytest

from app.domain.conversation import (
    _TEXTS,
    BRIEF_ORDER,
    Brief,
    Intent,
    classify,
    detect_language,
    detect_services,
    question,
    reply_is_safe,
    summary,
    text,
    with_disclosure,
)
from app.domain.persona import PERSONA, Language
from app.domain.scoring import Service


@pytest.mark.parametrize("lang", list(Language))
def test_first_message_disclosure_in_every_language(lang: Language) -> None:
    body = with_disclosure(text("welcome", lang), lang)
    assert body.startswith(PERSONA[lang].disclosure)
    assert "AI" in body.splitlines()[0]


@pytest.mark.parametrize(
    ("message", "lang"),
    [
        ("Assalomu alaykum, menga sayt kerak", Language.UZ),
        ("Salom! Narxi qancha?", Language.UZ),
        ("Ассалому алайкум, менга бот керак", Language.UZ_CYRL),
        ("Қанча туради?", Language.UZ_CYRL),
        ("Здравствуйте, нужен сайт для магазина", Language.RU),
        ("Hello, I need a website", Language.EN),
        ("👍", Language.UZ),  # no letters -> default
    ],
)
def test_language_detection(message: str, lang: Language) -> None:
    assert detect_language(message) is lang


@pytest.mark.parametrize(
    "message",
    [
        "kerak emas",
        "Rahmat, kerak emas",
        "boshqa yozmang",
        "керак эмас",
        "Не пишите мне больше",
        "отписаться",
        "STOP",
        "please unsubscribe me",
        "Стоп",
    ],
)
def test_opt_out_in_uz_ru_en_always_wins(message: str) -> None:
    assert classify(message) is Intent.OPT_OUT


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("Siz botmisiz?", Intent.BOT_QUESTION),
        ("Вы бот или человек?", Intent.BOT_QUESTION),
        ("Are you a bot?", Intent.BOT_QUESTION),
        ("odam bilan gaplashmoqchiman", Intent.HUMAN_REQUEST),
        ("Можно с человеком поговорить?", Intent.HUMAN_REQUEST),
        ("Qancha turadi?", Intent.PRICE_REQUEST),
        ("Сколько стоит бот?", Intent.PRICE_REQUEST),
        ("how much is it", Intent.PRICE_REQUEST),
        ("Menga sayt kerak", Intent.INTEREST),
        ("Хочу заказать бота", Intent.INTEREST),
        ("ha", Intent.CONFIRM),
        ("Hammasi to'g'ri", Intent.CONFIRM),
        ("Да, верно", Intent.CONFIRM),
        ("yes", Intent.CONFIRM),
        ("yo'q", Intent.DENY),
        ("Нет", Intent.DENY),
        ("Salom", Intent.GREETING),
        ("Earn $500 a day crypto signal", Intent.SPAM),
        ("asdf", Intent.OTHER),
    ],
)
def test_intents(message: str, intent: Intent) -> None:
    assert classify(message) is intent


def test_confirmation_must_be_explicit() -> None:
    # A long message that merely contains "ha" is not a confirmation.
    assert classify("ha, lekin dizaynni o'zgartiring") is not Intent.CONFIRM
    assert classify("Да, но добавьте каталог") is not Intent.CONFIRM


@pytest.mark.parametrize("lang", list(Language))
def test_bot_question_answer_is_truthful(lang: Language) -> None:
    answer = text("bot_answer", lang)
    assert "AI" in answer
    assert re.search(r"inson emas|инсон эмас|не человек|not a human", answer)


@pytest.mark.parametrize("lang", list(Language))
def test_no_reply_text_ever_contains_a_price(lang: Language) -> None:
    for key, by_lang in _TEXTS.items():
        body = by_lang[lang].replace("{owner}", "X").replace("{contact}", "Y")
        assert reply_is_safe(body, lang), key
        assert not re.search(r"so'm|сум|сўм|\$|usd|руб|тенге|narx(?:i)?\s*\d", body, re.I), key


def test_every_brief_question_exists_in_every_language() -> None:
    for lang in Language:
        for f in BRIEF_ORDER:
            assert question(f, lang)


def test_brief_records_answers_services_and_budget() -> None:
    brief = Brief()
    answers = [
        "Telegram bot va sayt",
        "Buyurtma olish",
        "katalog",
        "yo'q",
        "ha",
        "2 hafta ichida",
        "Lazzat, Ali, +998901234567",
    ]
    for a in answers[:3]:
        brief.record(a)
    brief.record("Budjetim 3 mln so'm")  # examples answer happens to mention money
    for a in answers[4:]:
        brief.record(a)
    assert brief.next_field() is None
    assert brief.services == [Service.BUSINESS_WEBSITE.value, Service.TELEGRAM_BOT.value]
    assert brief.budget_note == "Budjetim 3 mln so'm"
    shown = summary(brief, Language.UZ)
    assert "mln" not in shown and "2 hafta" not in shown  # figures never echoed
    assert "+998901234567" in shown  # the client's own contact is fine
    assert shown.rstrip().endswith("deb javob bering.")
    assert reply_is_safe(shown, Language.UZ)


def test_service_keywords() -> None:
    assert detect_services("internet do'kon kerak") == [Service.ECOMMERCE]
    assert detect_services("saytni yangilash") == [Service.WEBSITE_MODERNIZATION]
    assert detect_services("CRM и бот") == [Service.TELEGRAM_BOT, Service.CRM]


def test_language_switch_needs_clear_evidence() -> None:
    from app.domain.conversation import switch_language

    contact = "Lazzat Oshxonasi, Ali, +998901234567"
    assert switch_language(Language.UZ, contact) is Language.UZ  # names never switch
    assert switch_language(Language.UZ, "Давайте лучше по-русски") is Language.RU
    assert switch_language(Language.RU, "Hello, can we talk English") is Language.EN
    assert switch_language(Language.EN, "menga sayt kerak edi") is Language.UZ
    assert detect_language("Siz botmisiz?") is Language.UZ
