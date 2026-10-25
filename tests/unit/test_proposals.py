"""Offer builder: evidence-only observations, no prices, persona rules (M7)."""

from __future__ import annotations

import re

import pytest

from app.domain.persona import PERSONA, Language, language_for_country
from app.domain.proposals import (
    MAX_SERVICES,
    Observation,
    OfferInput,
    build_offer,
    pick_services,
    template_language,
)
from app.domain.quality_gate import Verdict, review
from app.domain.scoring import Service

ALL = [(s, 0.9) for s in Service]


def _offer(lang: Language = Language.UZ, **kw: object):  # type: ignore[no-untyped-def]
    data = {
        "company_name": "Lazzat Oshxonasi",
        "language": lang,
        "observations": [
            Observation("no_online_inquiry", is_fact=False),
            Observation("no_website", is_fact=True),
        ],
        "services": [(Service.BUSINESS_WEBSITE, 0.9), (Service.TELEGRAM_BOT, 0.5)],
    }
    data.update(kw)
    return build_offer(OfferInput(**data))  # type: ignore[arg-type]


@pytest.mark.parametrize("lang", list(Language))
def test_every_language_passes_the_gate(lang: Language) -> None:
    offer = _offer(lang, services=ALL)
    result = review(offer.body, language=offer.language, evidence_count=2)
    assert result.verdict is Verdict.APPROVED, result.issues


@pytest.mark.parametrize("lang", [Language.UZ, Language.RU, Language.EN])
def test_disclosure_first_opt_out_and_signature(lang: Language) -> None:
    body = _offer(lang).body
    persona = PERSONA[lang]
    assert body.startswith(persona.disclosure)
    assert persona.opt_out in body and body.rstrip().endswith(persona.signature)
    assert "Lazzat Oshxonasi" in body


@pytest.mark.parametrize("lang", list(Language))
def test_no_amounts_or_currency_ever(lang: Language) -> None:
    body = _offer(lang, services=ALL).body
    assert not re.search(r"\d", body)  # no number at all: no price, deadline or amount
    assert not re.search(r"so'm|сум|\$|usd|руб|тенге", body, re.I)


def test_facts_first_and_inferences_are_possibilities() -> None:
    offer = _offer()
    assert offer.observation_keys == ["no_website", "no_online_inquiry"]
    lines = offer.body.splitlines()
    fact = next(i for i, line in enumerate(lines) if "sayti ko'rsatilmagan" in line)
    guess = next(i for i, line in enumerate(lines) if line.startswith("• Ehtimol"))
    assert fact < guess
    assert "assume.inferences_marked" in offer.assumptions


def test_unknown_findings_are_not_mentioned() -> None:
    offer = _offer(observations=[Observation("made_up", True), Observation("no_https", True)])
    assert offer.observation_keys == ["no_https"]
    assert "made_up" not in offer.body


def test_service_selection() -> None:
    assert len(pick_services(ALL)) == MAX_SERVICES
    weak = [(Service.CRM, 0.1), (Service.TELEGRAM_BOT, 0.6)]
    assert pick_services(weak) == [Service.TELEGRAM_BOT]
    offer = _offer(services=[(Service.CRM, 0.1)])
    assert offer.services == []
    assert offer.open_questions == ["question.goal"]


def test_questions_follow_services() -> None:
    offer = _offer()
    assert offer.open_questions == [
        "question.business_website",
        "question.telegram_bot",
        "question.goal",
    ]


def test_languages() -> None:
    assert language_for_country("uz") is Language.UZ
    assert language_for_country("KZ") is Language.RU
    assert language_for_country("TJ") is Language.RU
    assert language_for_country("DE") is Language.EN
    assert template_language(Language.UZ_CYRL) is Language.UZ
    assert _offer(Language.UZ_CYRL).language is Language.UZ
