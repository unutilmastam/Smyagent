"""Company persistence and duplicate detection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.companies import (
    normalize_city,
    normalize_country,
    normalize_domain,
    normalize_name,
)
from app.domain.contacts import ContactKind, is_role_email, normalize_contact
from app.domain.errors import DomainError
from app.infrastructure.database.models import Company, CompanyDomain, CompanySource, Contact
from app.infrastructure.database.types import utcnow


@dataclass(frozen=True)
class NewCompany:
    name: str
    country: str
    city: str | None = None
    industry: str | None = None
    domains: tuple[str, ...] = ()
    source_type: str = "manual"
    source_url: str | None = None
    external_id: str | None = None
    retrieved_at: datetime | None = None
    is_fixture: bool = False
    phones: tuple[str, ...] = ()
    emails: tuple[str, ...] = ()
    telegrams: tuple[str, ...] = ()
    notes: str | None = None
    # Owner confirmed that a same-name company in the same city is a different business.
    allow_name_city_duplicate: bool = False

    def contacts(self) -> list[tuple[ContactKind, str]]:
        """Normalized, de-duplicated contacts. Raises DomainError on an invalid value."""
        items: list[tuple[ContactKind, str]] = []
        for kind, values in (
            (ContactKind.PHONE, self.phones),
            (ContactKind.EMAIL, self.emails),
            (ContactKind.TELEGRAM, self.telegrams),
        ):
            for raw in values:
                if raw.strip():
                    items.append((kind, normalize_contact(kind, raw, country=self.country)))
        return list(dict.fromkeys(items))


class DuplicateCompanyError(DomainError):
    def __init__(self, existing_id: uuid.UUID, reason: str) -> None:
        super().__init__(f"company already exists ({reason})")
        self.existing_id = existing_id
        self.reason = reason


class CompanyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, company_id: uuid.UUID) -> Company | None:
        return self.session.get(Company, company_id)

    def find_by_domain(self, domain: str) -> Company | None:
        normalized = normalize_domain(domain)
        stmt = (
            select(Company)
            .join(CompanyDomain, CompanyDomain.company_id == Company.id)
            .where(CompanyDomain.domain == normalized)
        )
        return self.session.scalars(stmt).first()

    def find_by_name_city(self, name: str, city: str | None) -> list[Company]:
        stmt = select(Company).where(Company.normalized_name == normalize_name(name))
        normalized_city = normalize_city(city)
        if normalized_city is None:
            stmt = stmt.where(Company.normalized_city.is_(None))
        else:
            stmt = stmt.where(Company.normalized_city == normalized_city)
        return list(self.session.scalars(stmt))

    def find_by_contact(self, kind: ContactKind, value: str) -> Company | None:
        stmt = (
            select(Company)
            .join(Contact, Contact.company_id == Company.id)
            .where(Contact.kind == kind, Contact.value == value)
        )
        return self.session.scalars(stmt).first()

    def find_duplicate(self, data: NewCompany) -> tuple[Company, str] | None:
        """Existing company matching by domain, phone/email/Telegram, or name + city.

        Domain and contact matches are hard duplicates. A name + city match is reported
        unless the owner explicitly allowed it (`allow_name_city_duplicate`).
        """
        for domain in data.domains:
            existing = self.find_by_domain(domain)
            if existing is not None:
                return existing, "domain"
        for kind, value in data.contacts():
            existing = self.find_by_contact(kind, value)
            if existing is not None:
                return existing, kind.value
        if not data.allow_name_city_duplicate:
            matches = self.find_by_name_city(data.name, data.city)
            if matches:
                return matches[0], "name+city"
        return None

    def add(self, data: NewCompany) -> Company:
        """Create a company with its domains and source. Raises on duplicates."""
        duplicate = self.find_duplicate(data)
        if duplicate is not None:
            raise DuplicateCompanyError(duplicate[0].id, duplicate[1])
        domains = list(dict.fromkeys(normalize_domain(d) for d in data.domains))
        contacts = data.contacts()
        company = Company(
            name=data.name.strip(),
            normalized_name=normalize_name(data.name),
            country=normalize_country(data.country),
            city=data.city.strip() if data.city else None,
            normalized_city=normalize_city(data.city),
            industry=data.industry.strip() if data.industry else None,
            notes=data.notes.strip() if data.notes else None,
        )
        company.domains = [
            CompanyDomain(domain=d, is_primary=(i == 0)) for i, d in enumerate(domains)
        ]
        company.sources = [
            CompanySource(
                source_type=data.source_type,
                source_url=data.source_url,
                external_id=data.external_id,
                retrieved_at=data.retrieved_at or utcnow(),
                is_fixture=data.is_fixture,
            )
        ]
        self.session.add(company)
        self.session.flush()
        source = company.sources[0]
        for kind, value in contacts:
            self.session.add(
                Contact(
                    company_id=company.id,
                    kind=kind,
                    value=value,
                    is_role_address=kind is ContactKind.EMAIL and is_role_email(value),
                    source_id=source.id,
                )
            )
        self.session.flush()
        return company

    def contacts_of(self, company_id: uuid.UUID) -> list[Contact]:
        stmt = (
            select(Contact)
            .where(Contact.company_id == company_id)
            .order_by(Contact.kind, Contact.value)
        )
        return list(self.session.scalars(stmt))

    def list(
        self, *, country: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Company]:
        stmt = select(Company).options(selectinload(Company.domains))
        if country:
            stmt = stmt.where(Company.country == normalize_country(country))
        stmt = stmt.order_by(Company.created_at.desc(), Company.id).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))
