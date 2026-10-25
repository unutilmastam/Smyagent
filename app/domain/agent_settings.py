"""Owner-editable agent settings (validated, versioned). Pure.

Each agent has one settings model with safe bounds. What the owner can change is
behaviour inside the hard rules; the hard rules themselves (HARD_RULES) are not
settings and no value here can switch them off (CLAUDE.md §4, §5, §13A).
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.agents import AgentModule
from app.domain.persona import Language
from app.domain.proposals import FRAME_PARTS, MAX_SERVICES, MIN_STRENGTH, OfferConfig
from app.domain.scoring import HOT_LEAD_THRESHOLD, Service

MAX_INSTRUCTIONS = 1000
MAX_TEXT = 600
MAX_WORDS = 50
EDITABLE_LANGUAGES = (Language.UZ, Language.RU, Language.EN)
PLACEHOLDERS = ("{company}", "{owner}")
_BRACES = re.compile(r"\{[^{}]*\}")

# Shown on the settings page as locked; enforced in code, never configurable.
HARD_RULES = (
    "rule.ai_disclosure",
    "rule.no_prices",
    "rule.opt_out",
    "rule.kill_switch",
    "rule.lawful_sources",
    "rule.owner_approval",
)


class _Settings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    # Free-text guidance for the agent. Used by AI-backed steps once an AI key is
    # configured (ADR-0007); always subordinate to HARD_RULES.
    instructions: str = Field("", max_length=MAX_INSTRUCTIONS)

    @field_validator("instructions")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class DiscoverySettings(_Settings):
    results_per_search: int = Field(50, ge=5, le=200)


class ResearchSettings(_Settings):
    companies_per_run: int = Field(20, ge=1, le=100)


class ScoringExtraSettings(_Settings):
    hot_lead_threshold: int = Field(HOT_LEAD_THRESHOLD, ge=0, le=100)


def _check_template(text: str) -> str:
    text = text.strip()
    if len(text) > MAX_TEXT:
        raise ValueError(f"text longer than {MAX_TEXT} characters")
    unknown = [m for m in _BRACES.findall(text) if m not in PLACEHOLDERS]
    if unknown or text.count("{") != text.count("}"):
        raise ValueError("only {company} and {owner} placeholders are allowed")
    return text


class ProposalSettings(_Settings):
    enabled_services: list[Service] = Field(default_factory=lambda: list(Service))
    max_services: int = Field(MAX_SERVICES, ge=1, le=5)
    min_strength: float = Field(MIN_STRENGTH, ge=0.1, le=0.9)
    # language -> part (title/greeting/intro/services/next) -> text; empty = built-in
    texts: dict[Language, dict[str, str]] = Field(default_factory=dict)
    # language -> service -> pitch line; empty = built-in
    service_texts: dict[Language, dict[Service, str]] = Field(default_factory=dict)

    @field_validator("texts")
    @classmethod
    def _texts(cls, value: dict[Language, dict[str, str]]) -> dict[Language, dict[str, str]]:
        clean: dict[Language, dict[str, str]] = {}
        for lang, parts in value.items():
            kept = {k: _check_template(v) for k, v in parts.items() if k in FRAME_PARTS}
            if kept := {k: v for k, v in kept.items() if v}:
                clean[lang] = kept
        return clean

    @field_validator("service_texts")
    @classmethod
    def _service_texts(
        cls, value: dict[Language, dict[Service, str]]
    ) -> dict[Language, dict[Service, str]]:
        clean: dict[Language, dict[Service, str]] = {}
        for lang, items in value.items():
            if kept := {s: t for s, v in items.items() if (t := _check_template(v))}:
                clean[lang] = kept
        return clean

    def offer_config(self) -> OfferConfig:
        return OfferConfig(
            enabled_services=frozenset(self.enabled_services),
            max_services=self.max_services,
            min_strength=self.min_strength,
            texts={lang: dict(parts) for lang, parts in self.texts.items()},
            service_texts={lang: dict(items) for lang, items in self.service_texts.items()},
        )


def parse_words(raw: str) -> list[str]:
    """One word/phrase per line or comma; trimmed, de-duplicated, bounded."""
    words = [w.strip() for w in re.split(r"[\n,]", raw)]
    return list(dict.fromkeys(w for w in words if w))


class QualityGateSettings(_Settings):
    extra_blocked: list[str] = Field(default_factory=list, max_length=MAX_WORDS)
    extra_review: list[str] = Field(default_factory=list, max_length=MAX_WORDS)

    @field_validator("extra_blocked", "extra_review")
    @classmethod
    def _words(cls, value: list[str]) -> list[str]:
        words = list(dict.fromkeys(w.strip() for w in value if w.strip()))
        for word in words:
            if not 2 <= len(word) <= 40:
                raise ValueError("each word must be 2-40 characters")
        return words


class ReplyMode(str, Enum):
    APPROVE_ALL = "approve_all"  # default: every reply waits for the owner (CLAUDE.md §8.1)
    AUTO_SAFE = "auto_safe"  # gate-clean template replies go out at once; others wait


class ConversationSettings(_Settings):
    reply_mode: ReplyMode = ReplyMode.APPROVE_ALL
    # Shown to the client on a human handoff (CLAUDE.md §5.1 rule 4).
    owner_contact: str = Field("Telegram: @ITcoDe_Uz", min_length=3, max_length=120)
    # Outreach (M9). Approved offers are emailed to public business addresses only.
    email_auto_approve: bool = False  # also send gate-clean offers without your tap
    email_daily_cap: int = Field(30, ge=1, le=100)
    email_warmup_start: int = Field(10, ge=1, le=100)
    email_warmup_step: int = Field(5, ge=0, le=50)
    email_min_gap_minutes: int = Field(3, ge=1, le=60)
    follow_up_days: int = Field(5, ge=5, le=30)
    telegram_daily_cap: int = Field(20, ge=1, le=50)

    @field_validator("owner_contact")
    @classmethod
    def _contact(cls, value: str) -> str:
        return value.strip()


class InstructionsOnly(_Settings):
    """Agents whose behaviour settings arrive with their milestone (M8, M9)."""


SETTINGS_MODELS: dict[AgentModule, type[_Settings]] = {
    AgentModule.ORCHESTRATOR: InstructionsOnly,
    AgentModule.DISCOVERY: DiscoverySettings,
    AgentModule.RESEARCH_AUDIT: ResearchSettings,
    AgentModule.OPPORTUNITY_SCORING: ScoringExtraSettings,
    AgentModule.PROPOSAL_REQUIREMENTS: ProposalSettings,
    AgentModule.QUALITY_GATE: QualityGateSettings,
    AgentModule.CONVERSATION: ConversationSettings,
}


def defaults(module: AgentModule) -> _Settings:
    return SETTINGS_MODELS[module]()


def load(module: AgentModule, values: dict[str, object] | None) -> _Settings:
    """Stored values -> model. Invalid stored data falls back to safe defaults."""
    try:
        return SETTINGS_MODELS[module].model_validate(values or {})
    except ValueError:
        return defaults(module)
