"""Opportunity analysis and lead scoring (CLAUDE.md §8.1 Opportunity & Scoring). Pure.

Opportunities are derived only from recorded findings (verified facts or labeled
inferences) — never invented. The score is a weighted average of explainable
components; components without data are reported as missing, never imputed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SCORING_VERSION = "v1"


class Service(str, Enum):
    BUSINESS_WEBSITE = "business_website"
    LANDING_PAGE = "landing_page"
    ECOMMERCE = "ecommerce"
    TELEGRAM_BOT = "telegram_bot"
    AUTOMATION = "automation"
    CRM = "crm"
    AI_ASSISTANT = "ai_assistant"
    WEBSITE_MODERNIZATION = "website_modernization"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True)
class FindingInput:
    key: str
    is_fact: bool
    confidence: float


# finding key -> (service, strength 0..1). Inferences are scaled by their confidence.
OPPORTUNITY_RULES: dict[str, tuple[tuple[Service, float], ...]] = {
    "no_website": ((Service.BUSINESS_WEBSITE, 0.9), (Service.TELEGRAM_BOT, 0.5)),
    "website_unreachable": ((Service.WEBSITE_MODERNIZATION, 0.7), (Service.MAINTENANCE, 0.6)),
    "http_error": ((Service.MAINTENANCE, 0.7),),
    "not_mobile_friendly": ((Service.WEBSITE_MODERNIZATION, 0.8),),
    "no_https": ((Service.MAINTENANCE, 0.6), (Service.WEBSITE_MODERNIZATION, 0.4)),
    "slow_response": ((Service.WEBSITE_MODERNIZATION, 0.5),),
    "weak_seo_metadata": ((Service.WEBSITE_MODERNIZATION, 0.4),),
    "no_visible_contacts": ((Service.WEBSITE_MODERNIZATION, 0.4),),
    "no_online_inquiry": ((Service.TELEGRAM_BOT, 0.7), (Service.AUTOMATION, 0.3)),
    "possibly_outdated": ((Service.MAINTENANCE, 0.5), (Service.WEBSITE_MODERNIZATION, 0.4)),
}


@dataclass(frozen=True)
class Opportunity:
    service: Service
    strength: float  # 0..1
    reasons: tuple[str, ...]  # finding keys supporting it


def derive_opportunities(findings: list[FindingInput]) -> list[Opportunity]:
    """Combine findings per service: strength = 1 - Π(1 - s_i) (independent signals)."""
    acc: dict[Service, tuple[float, list[str]]] = {}
    for f in findings:
        weight = 1.0 if f.is_fact else max(0.0, min(1.0, f.confidence))
        for service, strength in OPPORTUNITY_RULES.get(f.key, ()):
            s = strength * weight
            remaining, reasons = acc.get(service, (1.0, []))
            acc[service] = (remaining * (1 - s), [*reasons, f.key])
    result = [
        Opportunity(service, round(1 - remaining, 3), tuple(dict.fromkeys(reasons)))
        for service, (remaining, reasons) in acc.items()
    ]
    return sorted(result, key=lambda o: (-o.strength, o.service.value))


class Component(str, Enum):
    SERVICE_FIT = "service_fit"
    EVIDENCE_QUALITY = "evidence_quality"
    GEOGRAPHY = "geography"
    CONTACTABILITY = "contactability"
    ACTIVITY = "activity"


DEFAULT_WEIGHTS: dict[Component, float] = {
    Component.SERVICE_FIT: 3.0,
    Component.EVIDENCE_QUALITY: 1.0,
    Component.GEOGRAPHY: 1.0,
    Component.CONTACTABILITY: 2.0,
    Component.ACTIVITY: 1.0,
}
DEFAULT_QUALIFY_THRESHOLD = 55
HOT_LEAD_THRESHOLD = 75

GEOGRAPHY_POINTS = {"UZ": 100, "KZ": 60, "KG": 60, "TJ": 60}
CONTACT_POINTS = {"email": 40, "telegram": 35, "phone": 25}


@dataclass(frozen=True)
class ScoreInput:
    country: str
    findings: list[FindingInput]
    contact_kinds: frozenset[str]  # {"phone", "email", "telegram"} — role emails only
    researched: bool
    website_reachable: bool | None  # None = no website known
    recent_copyright: bool | None  # None = unknown


@dataclass(frozen=True)
class ComponentScore:
    component: Component
    value: int | None  # None = missing data (excluded, never imputed)
    explanation: str


@dataclass(frozen=True)
class ScoreResult:
    total: int
    components: list[ComponentScore]
    opportunities: list[Opportunity]
    missing: list[Component] = field(default_factory=list)
    version: str = SCORING_VERSION


def score(data: ScoreInput, weights: dict[Component, float] | None = None) -> ScoreResult:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    opportunities = derive_opportunities(data.findings)
    comps: list[ComponentScore] = []

    if data.researched:
        best = opportunities[0] if opportunities else None
        comps.append(
            ComponentScore(
                Component.SERVICE_FIT,
                round(100 * best.strength) if best else 0,
                f"best: {best.service.value} ({', '.join(best.reasons)})"
                if best
                else "no opportunity found",
            )
        )
        facts = sum(1 for f in data.findings if f.is_fact)
        comps.append(
            ComponentScore(
                Component.EVIDENCE_QUALITY,
                round(100 * facts / len(data.findings)) if data.findings else 50,
                f"{facts}/{len(data.findings)} findings are verified facts",
            )
        )
    else:
        comps.append(ComponentScore(Component.SERVICE_FIT, None, "not researched yet"))
        comps.append(ComponentScore(Component.EVIDENCE_QUALITY, None, "not researched yet"))

    geo = GEOGRAPHY_POINTS.get(data.country.upper())
    comps.append(ComponentScore(Component.GEOGRAPHY, geo, data.country.upper()))

    contact = min(100, sum(CONTACT_POINTS[k] for k in data.contact_kinds if k in CONTACT_POINTS))
    comps.append(
        ComponentScore(
            Component.CONTACTABILITY,
            contact,
            ", ".join(sorted(data.contact_kinds)) or "no public business contact",
        )
    )

    if data.website_reachable is None:
        comps.append(ComponentScore(Component.ACTIVITY, None, "no website to judge activity"))
    elif not data.website_reachable:
        comps.append(ComponentScore(Component.ACTIVITY, 30, "website does not open"))
    elif data.recent_copyright is None:
        comps.append(ComponentScore(Component.ACTIVITY, 70, "website opens; no dated content"))
    else:
        value = 100 if data.recent_copyright else 50
        comps.append(
            ComponentScore(
                Component.ACTIVITY,
                value,
                "recent copyright" if data.recent_copyright else "old copyright",
            )
        )

    present = [c for c in comps if c.value is not None]
    total_weight = sum(weights[c.component] for c in present)
    total = (
        round(sum(weights[c.component] * (c.value or 0) for c in present) / total_weight)
        if total_weight > 0
        else 0
    )
    missing = [c.component for c in comps if c.value is None]
    return ScoreResult(total=total, components=comps, opportunities=opportunities, missing=missing)


def qualifies(result: ScoreResult, threshold: int = DEFAULT_QUALIFY_THRESHOLD) -> bool:
    """A lead is QUALIFIED only with a real opportunity and a reachable channel."""
    contact = next(c for c in result.components if c.component is Component.CONTACTABILITY)
    return bool(result.opportunities) and (contact.value or 0) > 0 and result.total >= threshold
