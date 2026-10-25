"""Owner edits of agent settings: form parsing, validation and safety checks."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.agent_settings import (
    EDITABLE_LANGUAGES,
    SETTINGS_MODELS,
    ProposalSettings,
    QualityGateSettings,
    parse_words,
)
from app.domain.agents import AgentModule
from app.domain.proposals import FRAME_PARTS, Observation, OfferInput, build_offer
from app.domain.quality_gate import Verdict, review
from app.domain.scoring import Service
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository

SAMPLE_COMPANY = "Namuna MChJ"
_SERVICE_VALUES = {s.value for s in Service}
_NUMERIC = {
    AgentModule.DISCOVERY: ("results_per_search",),
    AgentModule.RESEARCH_AUDIT: ("companies_per_run",),
    AgentModule.OPPORTUNITY_SCORING: ("hot_lead_threshold",),
    AgentModule.PROPOSAL_REQUIREMENTS: ("max_services", "min_strength"),
}


@dataclass(frozen=True)
class SaveResult:
    ok: bool
    version: int = 0
    errors: tuple[str, ...] = ()


def values_from_form(
    module: AgentModule, form: Mapping[str, str], getlist: Callable[[str], list[str]]
) -> dict[str, Any]:
    """HTML form fields -> raw values for the module's settings model."""
    values: dict[str, Any] = {"instructions": form.get("instructions", "")}
    for name in _NUMERIC.get(module, ()):
        if form.get(name, "").strip():
            values[name] = form[name].strip()
    if module is AgentModule.PROPOSAL_REQUIREMENTS:
        values["enabled_services"] = [s for s in getlist("services") if s in _SERVICE_VALUES]
        values["texts"] = {
            lang.value: {part: form.get(f"text_{lang.value}_{part}", "") for part in FRAME_PARTS}
            for lang in EDITABLE_LANGUAGES
        }
        values["service_texts"] = {
            lang.value: {s.value: form.get(f"stext_{lang.value}_{s.value}", "") for s in Service}
            for lang in EDITABLE_LANGUAGES
        }
    if module is AgentModule.CONVERSATION:
        values["reply_mode"] = form.get("reply_mode", "approve_all")
        if form.get("owner_contact", "").strip():
            values["owner_contact"] = form["owner_contact"]
    if module is AgentModule.QUALITY_GATE:
        values["extra_blocked"] = parse_words(form.get("extra_blocked", ""))
        values["extra_review"] = parse_words(form.get("extra_review", ""))
    return values


def offer_text_problems(proposal: ProposalSettings, gate: QualityGateSettings) -> list[str]:
    """Build a sample offer per language with the owner's texts and run the Quality Gate.

    Every service is included so a price hidden in any pitch line is caught at save time.
    """
    config = dataclasses.replace(proposal.offer_config(), max_services=len(Service))
    problems: list[str] = []
    for lang in EDITABLE_LANGUAGES:
        draft = build_offer(
            OfferInput(
                company_name=SAMPLE_COMPANY,
                language=lang,
                observations=[Observation("no_website", is_fact=True)],
                services=[(service, 1.0) for service in Service],
            ),
            config,
        )
        result = review(
            draft.body,
            language=draft.language,
            evidence_count=1,
            extra_blocked=gate.extra_blocked,
            extra_review=gate.extra_review,
        )
        if result.verdict is Verdict.REJECTED:
            details = "; ".join(
                f"{i.code} ({i.detail})" if i.detail else i.code for i in result.issues
            )
            problems.append(f"{lang.value}: {details}")
    return problems


def _errors(exc: ValidationError) -> tuple[str, ...]:
    return tuple(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors())[
        :10
    ]


class AgentSettingsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = AgentSettingsRepository(session)

    def save(self, module: AgentModule, values: dict[str, Any], actor: Actor) -> SaveResult:
        try:
            settings: BaseModel = SETTINGS_MODELS[module].model_validate(values)
        except ValidationError as exc:
            return SaveResult(False, errors=_errors(exc))
        if isinstance(settings, ProposalSettings):
            gate = self.repo.get(AgentModule.QUALITY_GATE)
            if problems := offer_text_problems(settings, gate):
                return SaveResult(False, errors=tuple(problems))
        return SaveResult(True, version=self.repo.save(module, settings, actor))
