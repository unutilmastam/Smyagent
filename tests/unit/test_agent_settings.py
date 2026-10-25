"""Owner-editable agent settings: bounds, safe templates, effect on offers and gate."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.application.agent_settings import offer_text_problems, values_from_form
from app.domain.agent_settings import (
    DiscoverySettings,
    ProposalSettings,
    QualityGateSettings,
    defaults,
    load,
    parse_words,
)
from app.domain.agents import AgentModule
from app.domain.persona import Language
from app.domain.proposals import Observation, OfferInput, build_offer
from app.domain.quality_gate import review
from app.domain.scoring import Service


def _offer(settings: ProposalSettings, lang: Language = Language.UZ):  # type: ignore[no-untyped-def]
    return build_offer(
        OfferInput(
            company_name="Lazzat",
            language=lang,
            observations=[Observation("no_website", True)],
            services=[(s, 0.9) for s in Service],
        ),
        settings.offer_config(),
    )


def test_every_agent_has_safe_defaults() -> None:
    for module in AgentModule:
        assert defaults(module).instructions == ""
    assert defaults(AgentModule.DISCOVERY).results_per_search == 50  # type: ignore[attr-defined]


@pytest.mark.parametrize("value", [0, 4, 201])
def test_bounds_are_enforced(value: int) -> None:
    with pytest.raises(ValidationError):
        DiscoverySettings(results_per_search=value)


def test_invalid_stored_values_fall_back_to_defaults() -> None:
    assert load(AgentModule.DISCOVERY, {"results_per_search": 10_000}) == DiscoverySettings()
    assert load(AgentModule.DISCOVERY, None) == DiscoverySettings()
    assert load(AgentModule.DISCOVERY, {"results_per_search": 7, "junk": 1}).results_per_search == 7  # type: ignore[attr-defined]


def test_instructions_are_bounded_and_trimmed() -> None:
    assert DiscoverySettings(instructions="  qishloqlarni ham qidir  ").instructions == (
        "qishloqlarni ham qidir"
    )
    with pytest.raises(ValidationError):
        DiscoverySettings(instructions="x" * 1001)


@pytest.mark.parametrize("text", ["{company.__class__}", "{0}", "{owner", "salom {name}"])
def test_only_known_placeholders(text: str) -> None:
    with pytest.raises(ValidationError):
        ProposalSettings(texts={Language.UZ: {"intro": text}})


def test_owner_texts_and_service_choice_shape_the_offer() -> None:
    settings = ProposalSettings(
        enabled_services=[Service.TELEGRAM_BOT, Service.CRM],
        max_services=1,
        texts={Language.UZ: {"intro": "{company} uchun qisqa kuzatuv:", "title": ""}},
        service_texts={Language.UZ: {Service.CRM: "", Service.TELEGRAM_BOT: "Bot — {company}"}},
    )
    offer = _offer(settings)
    assert offer.services == [Service.CRM] or offer.services == [Service.TELEGRAM_BOT]
    assert len(offer.services) == 1
    assert "Lazzat uchun qisqa kuzatuv:" in offer.body
    assert offer.title == "Lazzat uchun taklif"  # empty override = built-in
    assert settings.texts == {Language.UZ: {"intro": "{company} uchun qisqa kuzatuv:"}}
    # Persona parts are never editable: disclosure, opt-out and signature stay.
    assert offer.body.startswith("Assalomu alaykum! Men Mustafo")
    assert "kerak emas" in offer.body


def test_disabled_services_are_never_offered() -> None:
    offer = _offer(ProposalSettings(enabled_services=[Service.CRM]))
    assert offer.services == [Service.CRM]
    assert _offer(ProposalSettings(enabled_services=[])).services == []


def test_price_in_owner_text_is_refused_at_save_time() -> None:
    gate = QualityGateSettings()
    clean = ProposalSettings(texts={Language.RU: {"next": "Напишите нам, {owner} ответит лично."}})
    assert offer_text_problems(clean, gate) == []
    priced = ProposalSettings(
        service_texts={Language.EN: {Service.MAINTENANCE: "Support from 50 USD per month"}}
    )
    problems = offer_text_problems(priced, gate)
    assert problems and problems[0].startswith("en:") and "price" in problems[0]


def test_owner_words_extend_the_gate() -> None:
    gate = QualityGateSettings(extra_blocked=["arzon"], extra_review=["tezkor"])
    body = _offer(ProposalSettings()).body
    result = review(
        body + "\nEng arzon va tezkor!",
        language=Language.UZ,
        evidence_count=1,
        extra_blocked=gate.extra_blocked,
        extra_review=gate.extra_review,
    )
    assert {"owner_blocked_word", "owner_review_word"} <= set(result.codes)
    # Whole words only, and regex characters are literal.
    assert (
        "owner_blocked_word"
        not in review(
            body + " arzonroq", language=Language.UZ, evidence_count=1, extra_blocked=["arzon"]
        ).codes
    )
    assert (
        "owner_blocked_word"
        in review(
            body + " a.b", language=Language.UZ, evidence_count=1, extra_blocked=["a.b"]
        ).codes
    )
    assert (
        "owner_blocked_word"
        not in review(
            body + " axb", language=Language.UZ, evidence_count=1, extra_blocked=["a.b"]
        ).codes
    )


def test_word_lists() -> None:
    assert parse_words("arzon\n tezkor, arzon,,\n") == ["arzon", "tezkor"]
    with pytest.raises(ValidationError):
        QualityGateSettings(extra_blocked=["x"])
    with pytest.raises(ValidationError):
        QualityGateSettings(extra_blocked=[f"w{i}" for i in range(51)])


def test_form_parsing() -> None:
    form = {
        "instructions": "ok",
        "max_services": "2",
        "min_strength": "",
        "text_uz_intro": "Salom {company}",
        "stext_ru_crm": "CRM",
    }
    values = values_from_form(
        AgentModule.PROPOSAL_REQUIREMENTS, form, lambda _n: ["crm", "nope", "telegram_bot"]
    )
    assert values["enabled_services"] == ["crm", "telegram_bot"]
    assert values["max_services"] == "2" and "min_strength" not in values
    settings = ProposalSettings.model_validate(values)
    assert settings.texts == {Language.UZ: {"intro": "Salom {company}"}}
    assert settings.service_texts == {Language.RU: {Service.CRM: "CRM"}}
    gate_values = values_from_form(AgentModule.QUALITY_GATE, {"extra_blocked": "a1\nb2"}, list)
    assert gate_values["extra_blocked"] == ["a1", "b2"] and gate_values["extra_review"] == []
