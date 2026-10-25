"""Company intake shared by manual entry, CSV import and search providers (M4)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.errors import DomainError
from app.infrastructure.repositories.companies import (
    CompanyRepository,
    DuplicateCompanyError,
    NewCompany,
)
from app.infrastructure.repositories.workflow import AuditLogRepository, WorkflowEventRepository
from app.infrastructure.search_providers.base import SearchProvider, SearchQuery


class IntakeStatus(str, Enum):
    CREATED = "created"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


@dataclass(frozen=True)
class IntakeResult:
    status: IntakeStatus
    company_id: uuid.UUID | None = None
    duplicate_of: uuid.UUID | None = None
    reason: str | None = None


class DiscoveryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.events = WorkflowEventRepository(session)
        self.audit = AuditLogRepository(session)

    def ingest(self, data: NewCompany, actor: Actor, *, dry_run: bool = False) -> IntakeResult:
        """Validate, de-duplicate and (unless dry_run) store one company.

        Duplicates are never merged automatically; they are reported for review.
        """
        try:
            duplicate = self.companies.find_duplicate(data)
            if duplicate is not None:
                return IntakeResult(
                    IntakeStatus.DUPLICATE, duplicate_of=duplicate[0].id, reason=duplicate[1]
                )
            if dry_run:
                self._validate_only(data)
                return IntakeResult(IntakeStatus.CREATED)
            with self.session.begin_nested():
                company = self.companies.add(data)
        except DuplicateCompanyError as exc:  # concurrent insert of the same domain
            return IntakeResult(
                IntakeStatus.DUPLICATE, duplicate_of=exc.existing_id, reason=exc.reason
            )
        except DomainError as exc:
            return IntakeResult(IntakeStatus.INVALID, reason=str(exc))
        self.events.record(
            entity_type="company",
            entity_id=company.id,
            from_state=None,
            to_state="NEW",
            actor=actor,
            reason=f"intake:{data.source_type}",
        )
        return IntakeResult(IntakeStatus.CREATED, company_id=company.id)

    def _validate_only(self, data: NewCompany) -> None:
        from app.domain.companies import normalize_country, normalize_domain, normalize_name

        normalize_name(data.name)
        normalize_country(data.country)
        for domain in data.domains:
            normalize_domain(domain)
        data.contacts()

    def search_and_ingest(
        self, provider: SearchProvider, query: SearchQuery, actor: Actor
    ) -> list[IntakeResult]:
        results = []
        for item in provider.search(query):
            results.append(
                self.ingest(
                    NewCompany(
                        name=item.name,
                        country=item.country,
                        city=item.city,
                        industry=item.industry,
                        domains=(item.domain,) if item.domain else (),
                        phones=item.phones,
                        source_type=provider.name,
                        source_url=item.source_url,
                        external_id=item.external_id,
                        is_fixture=provider.is_fixture,
                    ),
                    actor,
                )
            )
        self.audit.add(
            actor=actor,
            action="discovery.search",
            details={
                "provider": provider.name,
                "query": query.query[:100],
                "country": query.country,
                "created": sum(r.status is IntakeStatus.CREATED for r in results),
            },
        )
        return results
