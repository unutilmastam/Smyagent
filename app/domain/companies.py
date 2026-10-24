"""Company research state machine and identity normalization (CLAUDE.md §8.1, §9.1)."""

from __future__ import annotations

import re
import unicodedata
from enum import Enum
from urllib.parse import urlsplit

from app.domain.errors import DomainError, InvalidTransitionError

# Indexed string columns are capped at 191 chars so unique indexes fit older
# InnoDB/utf8mb4 limits (ADR-0002).
MAX_INDEXED_LENGTH = 191


class ResearchState(str, Enum):
    NEW = "NEW"
    RESEARCH_PENDING = "RESEARCH_PENDING"
    RESEARCHED = "RESEARCHED"
    ANALYZED = "ANALYZED"
    RESEARCH_FAILED = "RESEARCH_FAILED"
    ARCHIVED = "ARCHIVED"


_RESEARCH_TRANSITIONS: dict[ResearchState, frozenset[ResearchState]] = {
    ResearchState.NEW: frozenset({ResearchState.RESEARCH_PENDING, ResearchState.ARCHIVED}),
    ResearchState.RESEARCH_PENDING: frozenset(
        {ResearchState.RESEARCHED, ResearchState.RESEARCH_FAILED, ResearchState.ARCHIVED}
    ),
    ResearchState.RESEARCHED: frozenset(
        {ResearchState.ANALYZED, ResearchState.RESEARCH_PENDING, ResearchState.ARCHIVED}
    ),
    ResearchState.ANALYZED: frozenset({ResearchState.RESEARCH_PENDING, ResearchState.ARCHIVED}),
    ResearchState.RESEARCH_FAILED: frozenset(
        {ResearchState.RESEARCH_PENDING, ResearchState.ARCHIVED}
    ),
    ResearchState.ARCHIVED: frozenset({ResearchState.NEW}),
}


def can_transition_research(current: ResearchState, target: ResearchState) -> bool:
    return target in _RESEARCH_TRANSITIONS[current]


def ensure_research_transition(current: ResearchState, target: ResearchState) -> None:
    if not can_transition_research(current, target):
        raise InvalidTransitionError("company", current.value, target.value)


_SPACES = re.compile(r"\s+")
_APOSTROPHES = str.maketrans({"’": "'", "ʻ": "'", "ʼ": "'", "`": "'", "‘": "'"})  # noqa: RUF001
_LEGAL_FORMS = re.compile(
    # Latin and Cyrillic legal-form abbreviations (UZ/RU/KZ); Cyrillic is intentional.
    r"\b(ooo|mchj|llc|ltd|xk|ip|too|oao|zao|ao|ООО|МЧЖ|ТОО|ИП|ОАО|ЗАО|АО)\b\.?",  # noqa: RUF001
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[\"«»“”.,()]+")


def normalize_name(name: str) -> str:
    """Comparable company name: casefolded, legal form and quotes removed."""
    text = unicodedata.normalize("NFKC", name).translate(_APOSTROPHES)
    text = _PUNCT.sub(" ", text)
    text = _LEGAL_FORMS.sub(" ", text)
    text = _SPACES.sub(" ", text).strip().casefold()
    if not text:
        raise DomainError("company name is empty after normalization")
    return text[:MAX_INDEXED_LENGTH]


def normalize_city(city: str | None) -> str | None:
    if city is None:
        return None
    text = _SPACES.sub(" ", unicodedata.normalize("NFKC", city).translate(_APOSTROPHES))
    text = text.strip().casefold()
    return text[:MAX_INDEXED_LENGTH] or None


_DOMAIN_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def normalize_domain(value: str) -> str:
    """Bare lowercase host from a domain or URL: `https://www.Example.UZ/x` -> `example.uz`."""
    raw = value.strip()
    if not raw:
        raise DomainError("domain is empty")
    host = urlsplit(raw if "//" in raw else f"//{raw}").hostname or ""
    try:
        host = host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise DomainError("domain is not a valid hostname") from exc
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) < 2 or not all(_DOMAIN_LABEL.match(label) for label in labels):
        raise DomainError("domain is not a valid hostname")
    if labels[-1].isdigit():
        raise DomainError("IP addresses are not company domains")
    if len(host) > MAX_INDEXED_LENGTH:
        raise DomainError(f"domain longer than {MAX_INDEXED_LENGTH} characters")
    return host


def normalize_country(code: str) -> str:
    text = code.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", text):
        raise DomainError("country must be an ISO 3166-1 alpha-2 code, e.g. UZ")
    return text
