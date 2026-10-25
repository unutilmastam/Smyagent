from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.csv_import import MAX_ROWS, CsvFormatError, import_csv
from app.application.discovery import DiscoveryService, IntakeStatus
from app.domain.actors import Actor
from app.infrastructure.database.models import AuditLog, Company, CompanySource, Contact
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.infrastructure.repositories.workflow import WorkflowEventRepository
from app.infrastructure.search_providers.base import SearchQuery
from app.infrastructure.search_providers.fixture import FixtureSearchProvider

OWNER = Actor.user("owner")


def _count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _new(**kw: object) -> NewCompany:
    data: dict[str, object] = {"name": "Denov Savdo", "country": "UZ", "city": "Denov"}
    data.update(kw)
    return NewCompany(**data)  # type: ignore[arg-type]


def test_ingest_creates_company_contacts_and_event(session: Session) -> None:
    service = DiscoveryService(session)
    result = service.ingest(
        _new(
            domains=("denovsavdo.uz",),
            phones=("90 123 45 67",),
            emails=("Info@denovsavdo.uz", "aziz@denovsavdo.uz"),
            telegrams=("t.me/denov_savdo",),
        ),
        OWNER,
    )
    assert result.status is IntakeStatus.CREATED and result.company_id
    contacts = {
        (c.kind.value, c.value, c.is_role_address)
        for c in CompanyRepository(session).contacts_of(result.company_id)
    }
    assert contacts == {
        ("phone", "+998901234567", False),
        ("email", "info@denovsavdo.uz", True),
        ("email", "aziz@denovsavdo.uz", False),
        ("telegram", "@denov_savdo", False),
    }
    events = WorkflowEventRepository(session).history("company", result.company_id)
    assert [(e.from_state, e.to_state, e.reason) for e in events] == [
        (None, "NEW", "intake:manual")
    ]


@pytest.mark.parametrize(
    ("second", "reason"),
    [
        ({"name": "Other", "city": "Termiz", "domains": ("https://www.denovsavdo.uz",)}, "domain"),
        ({"name": "Other", "city": "Termiz", "phones": ("+998 90 123 45 67",)}, "phone"),
        ({"name": "Other", "city": "Termiz", "emails": ("INFO@denovsavdo.uz",)}, "email"),
        ({"name": "Other", "city": "Termiz", "telegrams": ("@Denov_Savdo",)}, "telegram"),
        ({"name": "DENOV SAVDO MCHJ"}, "name+city"),
    ],
)
def test_duplicates_are_reported_not_merged(
    session: Session, second: dict[str, object], reason: str
) -> None:
    service = DiscoveryService(session)
    first = service.ingest(
        _new(
            domains=("denovsavdo.uz",),
            phones=("901234567",),
            emails=("info@denovsavdo.uz",),
            telegrams=("@denov_savdo",),
        ),
        OWNER,
    )
    result = service.ingest(_new(**second), OWNER)
    assert result.status is IntakeStatus.DUPLICATE
    assert result.reason == reason and result.duplicate_of == first.company_id
    assert _count(session, Company) == 1


def test_owner_can_allow_same_name_and_city(session: Session) -> None:
    service = DiscoveryService(session)
    service.ingest(_new(), OWNER)
    assert (
        service.ingest(_new(allow_name_city_duplicate=True), OWNER).status is IntakeStatus.CREATED
    )
    # but never for a hard duplicate (same domain)
    service.ingest(_new(name="X", domains=("x.uz",)), OWNER)
    again = service.ingest(_new(name="X", domains=("x.uz",), allow_name_city_duplicate=True), OWNER)
    assert again.status is IntakeStatus.DUPLICATE and again.reason == "domain"


def test_invalid_input_stores_nothing(session: Session) -> None:
    result = DiscoveryService(session).ingest(_new(phones=("123",)), OWNER)
    assert result.status is IntakeStatus.INVALID and "digits" in (result.reason or "")
    assert _count(session, Company) == 0 and _count(session, Contact) == 0


def test_fixture_provider_results_are_labeled(session: Session) -> None:
    results = DiscoveryService(session).search_and_ingest(
        FixtureSearchProvider(), SearchQuery(country="UZ", query="savdo", city="Qarshi"), OWNER
    )
    assert [r.status for r in results] == [IntakeStatus.CREATED] * 3
    sources = session.scalars(select(CompanySource)).all()
    assert sources and all(s.is_fixture and s.source_type == "fixture" for s in sources)
    assert session.scalars(select(AuditLog.action)).all() == ["discovery.search"]


CSV_RU = (
    "Название;Страна;Город;Сайт;Телефон;Email\n"
    "Denov Savdo;UZ;Denov;denovsavdo.uz;90 123 45 67|91 000 00 00;info@denovsavdo.uz\n"
    "Termiz Mebel;UZ;Termiz;;;\n"
    ";UZ;;;;\n"
    "Bad Phone;UZ;Qarshi;;123;\n"
    "Denov Savdo MChJ;UZ;Denov;;;\n"
)


def test_csv_dry_run_previews_without_saving(session: Session) -> None:
    report = import_csv(session, CSV_RU.encode(), filename="leads.csv", actor=OWNER, dry_run=True)
    statuses = [(r.row, r.result.status.value) for r in report.rows]
    # row 6 duplicates row 2 *within the same file* and is still detected in the preview
    assert statuses == [
        (2, "created"),
        (3, "created"),
        (4, "invalid"),
        (5, "invalid"),
        (6, "duplicate"),
    ]
    assert (report.created, report.duplicates, report.invalid) == (2, 1, 2)
    assert _count(session, Company) == 0
    audit = session.scalars(select(AuditLog)).one()
    assert audit.details is not None and audit.details["dry_run"] is True


def test_csv_import_saves_with_sources(session: Session) -> None:
    report = import_csv(
        session, CSV_RU.encode("cp1251"), filename="../evil/leads.csv", actor=OWNER, dry_run=False
    )
    assert report.created == 2 and report.filename == ".._evil_leads.csv"
    company = session.scalars(select(Company).where(Company.name == "Denov Savdo")).one()
    phones = sorted(
        c.value
        for c in CompanyRepository(session).contacts_of(company.id)
        if c.kind.value == "phone"
    )
    assert phones == ["+998901234567", "+998910000000"]
    source = session.scalars(
        select(CompanySource).where(CompanySource.company_id == company.id)
    ).one()
    assert source.source_type == "csv" and source.external_id == ".._evil_leads.csv#2"


def test_csv_utf8_bom_comma_and_english_headers(session: Session) -> None:
    data = '﻿name,country,city,domain\n"Samarqand Non, MChJ",UZ,Samarqand,non.uz\n'.encode()
    report = import_csv(session, data, filename="a.csv", actor=OWNER, dry_run=False)
    assert report.created == 1
    assert session.scalars(select(Company.name)).one() == "Samarqand Non, MChJ"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"city,domain\nDenov,x.uz\n", "missing required"),
        (b"\x98\x98\x98", "UTF-8"),  # 0x98 is undefined in cp1251 and invalid UTF-8
        (("name,country\n" + "A,UZ\n" * (MAX_ROWS + 1)).encode(), "rows"),
        (b"x" * (1024 * 1024 + 1), "larger"),
    ],
)
def test_csv_format_errors(session: Session, data: bytes, message: str) -> None:
    with pytest.raises(CsvFormatError, match=message):
        import_csv(session, data, filename="x.csv", actor=OWNER, dry_run=True)
