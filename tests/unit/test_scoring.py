"""Opportunity derivation and explainable scoring (pure domain, M6)."""

from __future__ import annotations

from app.domain.scoring import (
    DEFAULT_QUALIFY_THRESHOLD,
    Component,
    FindingInput,
    ScoreInput,
    Service,
    derive_opportunities,
    qualifies,
    score,
)

FACT = True
INFERENCE = False


def _input(**overrides: object) -> ScoreInput:
    base: dict[str, object] = {
        "country": "UZ",
        "findings": [FindingInput("no_website", FACT, 1.0)],
        "contact_kinds": frozenset({"phone", "email"}),
        "researched": True,
        "website_reachable": None,
        "recent_copyright": None,
    }
    base.update(overrides)
    return ScoreInput(**base)  # type: ignore[arg-type]


def _component(result, component):  # type: ignore[no-untyped-def]
    return next(c for c in result.components if c.component is component)


def test_opportunities_come_only_from_known_findings() -> None:
    assert derive_opportunities([]) == []
    assert derive_opportunities([FindingInput("unknown_key", FACT, 1.0)]) == []
    opps = derive_opportunities([FindingInput("no_website", FACT, 1.0)])
    assert opps[0].service is Service.BUSINESS_WEBSITE and opps[0].strength == 0.9
    assert opps[0].reasons == ("no_website",)


def test_independent_signals_combine_and_inferences_are_scaled() -> None:
    opps = derive_opportunities(
        [
            FindingInput("not_mobile_friendly", FACT, 1.0),  # modernization 0.8
            FindingInput("slow_response", FACT, 1.0),  # modernization 0.5
        ]
    )
    modern = next(o for o in opps if o.service is Service.WEBSITE_MODERNIZATION)
    assert modern.strength == round(1 - 0.2 * 0.5, 3)
    assert modern.reasons == ("not_mobile_friendly", "slow_response")

    weak = derive_opportunities([FindingInput("possibly_outdated", INFERENCE, 0.5)])
    maintenance = next(o for o in weak if o.service is Service.MAINTENANCE)
    assert maintenance.strength == 0.25


def test_opportunities_sorted_by_strength() -> None:
    opps = derive_opportunities([FindingInput("no_website", FACT, 1.0)])
    assert [o.service for o in opps] == [Service.BUSINESS_WEBSITE, Service.TELEGRAM_BOT]


def test_missing_components_are_excluded_not_imputed() -> None:
    result = score(_input())
    activity = _component(result, Component.ACTIVITY)
    assert activity.value is None and result.missing == [Component.ACTIVITY]
    # (3*90 + 1*100 + 1*100 + 2*65) / 7 — activity contributes no weight at all.
    assert result.total == round(600 / 7)


def test_not_researched_marks_research_components_missing() -> None:
    result = score(_input(researched=False, findings=[]))
    assert {Component.SERVICE_FIT, Component.EVIDENCE_QUALITY} <= set(result.missing)
    assert result.opportunities == []
    assert not qualifies(result)


def test_unknown_country_geography_is_missing() -> None:
    result = score(_input(country="RU"))
    assert _component(result, Component.GEOGRAPHY).value is None
    assert Component.GEOGRAPHY in result.missing


def test_activity_levels() -> None:
    assert _component(score(_input(website_reachable=False)), Component.ACTIVITY).value == 30
    assert _component(score(_input(website_reachable=True)), Component.ACTIVITY).value == 70
    recent = score(_input(website_reachable=True, recent_copyright=True))
    old = score(_input(website_reachable=True, recent_copyright=False))
    assert _component(recent, Component.ACTIVITY).value == 100
    assert _component(old, Component.ACTIVITY).value == 50


def test_weights_change_the_total() -> None:
    default = score(_input(contact_kinds=frozenset({"phone"})))
    contact_heavy = score(
        _input(contact_kinds=frozenset({"phone"})), {Component.CONTACTABILITY: 10.0}
    )
    assert contact_heavy.total < default.total  # contactability (25) now dominates
    all_zero = score(_input(), dict.fromkeys(Component, 0.0))
    assert all_zero.total == 0


def test_score_is_reproducible() -> None:
    assert score(_input()) == score(_input())


def test_qualification_requires_opportunity_contact_and_threshold() -> None:
    good = score(_input())
    assert good.total >= DEFAULT_QUALIFY_THRESHOLD and qualifies(good)
    assert not qualifies(good, threshold=good.total + 1)
    no_contact = score(_input(contact_kinds=frozenset()))
    assert _component(no_contact, Component.CONTACTABILITY).value == 0
    assert not qualifies(no_contact, threshold=0)
    no_opportunity = score(_input(findings=[]))
    assert not qualifies(no_opportunity, threshold=0)


def test_explanations_name_the_evidence() -> None:
    fit = _component(score(_input()), Component.SERVICE_FIT)
    assert "business_website" in fit.explanation and "no_website" in fit.explanation
