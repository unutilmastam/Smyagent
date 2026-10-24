from __future__ import annotations

import pytest

from app.domain.companies import (
    ResearchState,
    can_transition_research,
    normalize_city,
    normalize_country,
    normalize_domain,
    normalize_name,
)
from app.domain.errors import DomainError

R = ResearchState


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.uz", "example.uz"),
        ("https://www.Example.UZ/about?x=1", "example.uz"),
        ("http://shop.example.uz:8080", "shop.example.uz"),
        ("EXAMPLE.uz.", "example.uz"),
        ("пример.рф", "xn--e1afmkfd.xn--p1ai"),
    ],
)
def test_normalize_domain(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize("raw", ["", "localhost", "192.168.0.1", "-bad.uz", "exa mple.uz"])
def test_normalize_domain_rejects(raw: str) -> None:
    with pytest.raises(DomainError):
        normalize_domain(raw)


def test_normalize_name_strips_legal_forms_and_quotes() -> None:
    assert normalize_name("ООО «Denov Savdo»") == normalize_name("Denov Savdo MChJ")
    assert normalize_name("  Denov   Savdo LLC ") == "denov savdo"
    assert normalize_name("O‘zbek Tekstil") == normalize_name("O'zbek tekstil")


def test_normalize_name_rejects_empty() -> None:
    with pytest.raises(DomainError):
        normalize_name("  LLC  ")


def test_normalize_city_and_country() -> None:
    assert normalize_city("  Termiz ") == "termiz"
    assert normalize_city(None) is None
    assert normalize_country(" uz ") == "UZ"
    with pytest.raises(DomainError):
        normalize_country("UZB")


def test_research_state_machine() -> None:
    assert can_transition_research(R.NEW, R.RESEARCH_PENDING)
    assert can_transition_research(R.RESEARCH_PENDING, R.RESEARCH_FAILED)
    assert can_transition_research(R.RESEARCH_FAILED, R.RESEARCH_PENDING)  # retry
    assert can_transition_research(R.RESEARCHED, R.ANALYZED)
    assert not can_transition_research(R.NEW, R.ANALYZED)
    assert not can_transition_research(R.NEW, R.RESEARCHED)
    assert not can_transition_research(R.ARCHIVED, R.ANALYZED)
