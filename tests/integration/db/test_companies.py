from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.models import CompanyDomain
from app.infrastructure.repositories.companies import (
    CompanyRepository,
    DuplicateCompanyError,
    NewCompany,
)


def _company(**kw: object) -> NewCompany:
    data: dict[str, object] = {"name": "Denov Savdo MChJ", "country": "uz", "city": "Denov"}
    data.update(kw)
    return NewCompany(**data)  # type: ignore[arg-type]


def test_add_normalizes_and_keeps_source(session: Session) -> None:
    repo = CompanyRepository(session)
    company = repo.add(
        _company(domains=("https://www.DenovSavdo.uz/", "denovsavdo.uz"), source_type="csv")
    )
    session.commit()

    loaded = repo.get(company.id)
    assert loaded is not None
    assert loaded.normalized_name == "denov savdo"
    assert loaded.country == "UZ"
    assert [d.domain for d in loaded.domains] == ["denovsavdo.uz"]  # deduplicated
    assert loaded.domains[0].is_primary
    assert loaded.sources[0].source_type == "csv"
    assert loaded.sources[0].is_fixture is False
    assert loaded.created_at.tzinfo is not None


def test_duplicate_by_domain(session: Session) -> None:
    repo = CompanyRepository(session)
    first = repo.add(_company(domains=("example.uz",)))
    with pytest.raises(DuplicateCompanyError) as exc:
        repo.add(_company(name="Other name", city="Termiz", domains=("http://example.uz/x",)))
    assert exc.value.existing_id == first.id
    assert exc.value.reason == "domain"


def test_duplicate_by_name_and_city(session: Session) -> None:
    repo = CompanyRepository(session)
    repo.add(_company())
    with pytest.raises(DuplicateCompanyError) as exc:
        repo.add(_company(name='ООО "Denov Savdo"', city=" denov "))
    assert exc.value.reason == "name+city"
    # Same name in another city is a different company.
    assert repo.add(_company(city="Termiz")).city == "Termiz"


def test_domain_unique_constraint_enforced_by_database(session: Session) -> None:
    repo = CompanyRepository(session)
    a = repo.add(_company(domains=("a.uz",)))
    session.commit()
    session.add(CompanyDomain(id=uuid.uuid4(), company_id=a.id, domain="a.uz"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_fixture_sources_are_flagged(session: Session) -> None:
    company = CompanyRepository(session).add(_company(source_type="fixture", is_fixture=True))
    assert company.sources[0].is_fixture is True


def test_unicode_round_trip(session: Session) -> None:
    repo = CompanyRepository(session)
    company = repo.add(_company(name="Ўзбекистон Текстиль 🧵", city="Тошкент"))
    session.commit()
    session.expire_all()
    loaded = repo.get(company.id)
    assert loaded is not None and loaded.name == "Ўзбекистон Текстиль 🧵"


def test_list_filters_and_paginates(session: Session) -> None:
    repo = CompanyRepository(session)
    for i in range(3):
        repo.add(_company(name=f"Firm {i}", country="UZ"))
    repo.add(_company(name="Almaty Firm", country="KZ", city="Almaty"))
    session.commit()
    assert len(repo.list(country="uz")) == 3
    assert len(repo.list(limit=2)) == 2
    assert len(repo.list(limit=10, offset=3)) == 1
