"""Read-side use cases for the dashboard and API: company search and detail."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.companies import ResearchState, normalize_country
from app.domain.errors import DomainError
from app.infrastructure.database.models import (
    Company,
    CompanyDomain,
    CompanySource,
    Contact,
    Lead,
    LeadScore,
    Opportunity,
    ResearchFinding,
    ResearchRun,
    WebsiteAudit,
    WorkflowEvent,
)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 100


class CompanySort(str, Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    NAME = "name"


@dataclass(frozen=True)
class CompanyQuery:
    q: str = ""
    country: str | None = None
    state: ResearchState | None = None
    sort: CompanySort = CompanySort.NEWEST
    page: int = 1
    per_page: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            raise DomainError("page must be >= 1")
        if not 1 <= self.per_page <= MAX_PAGE_SIZE:
            raise DomainError(f"per_page must be between 1 and {MAX_PAGE_SIZE}")


@dataclass(frozen=True)
class CompanyRow:
    id: uuid.UUID
    name: str
    country: str
    city: str | None
    industry: str | None
    research_state: ResearchState
    primary_domain: str | None
    lead_stage: str | None
    is_fixture: bool = False


@dataclass(frozen=True)
class CompanyPage:
    items: list[CompanyRow]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.per_page))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


@dataclass(frozen=True)
class CompanyDetail:
    company: Company
    lead: Lead | None
    research_runs: list[ResearchRun] = field(default_factory=list)
    contacts: list[Contact] = field(default_factory=list)
    latest_audit: WebsiteAudit | None = None
    opportunities: list[Opportunity] = field(default_factory=list)
    latest_score: LeadScore | None = None
    findings: list[ResearchFinding] = field(default_factory=list)
    history: list[WorkflowEvent] = field(default_factory=list)


def _like_pattern(text: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class CompanyQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: CompanyQuery) -> CompanyPage:
        conditions = []
        text = query.q.strip()[:MAX_QUERY_LENGTH].casefold()
        if text:
            pattern = _like_pattern(text)
            domain_match = (
                select(CompanyDomain.company_id)
                .where(CompanyDomain.domain.like(pattern, escape="\\"))
                .scalar_subquery()
            )
            conditions.append(
                or_(
                    Company.normalized_name.like(pattern, escape="\\"),
                    Company.id.in_(domain_match),
                )
            )
        if query.country:
            conditions.append(Company.country == normalize_country(query.country))
        if query.state is not None:
            conditions.append(Company.research_state == query.state)

        total = int(
            self.session.scalar(select(func.count()).select_from(Company).where(*conditions)) or 0
        )
        order: dict[CompanySort, tuple[ColumnElement[Any], ...]] = {
            CompanySort.NEWEST: (Company.created_at.desc(), Company.id.asc()),
            CompanySort.OLDEST: (Company.created_at.asc(), Company.id.asc()),
            CompanySort.NAME: (Company.normalized_name.asc(), Company.id.asc()),
        }
        fixture = (
            exists()
            .where(CompanySource.company_id == Company.id, CompanySource.is_fixture.is_(True))
            .label("is_fixture")
        )
        stmt = (
            select(Company, Lead.stage, fixture)
            .outerjoin(Lead, Lead.company_id == Company.id)
            .options(selectinload(Company.domains))
            .where(*conditions)
            .order_by(*order[query.sort])
            .limit(query.per_page)
            .offset((query.page - 1) * query.per_page)
        )
        items = []
        for company, stage, is_fixture in self.session.execute(stmt).all():
            primary = next((d.domain for d in company.domains if d.is_primary), None)
            items.append(
                CompanyRow(
                    id=company.id,
                    name=company.name,
                    country=company.country,
                    city=company.city,
                    industry=company.industry,
                    research_state=company.research_state,
                    primary_domain=primary
                    or (company.domains[0].domain if company.domains else None),
                    lead_stage=stage.value if stage is not None else None,
                    is_fixture=bool(is_fixture),
                )
            )
        return CompanyPage(items=items, total=total, page=query.page, per_page=query.per_page)

    def countries(self) -> list[str]:
        stmt = select(Company.country).distinct().order_by(Company.country)
        return list(self.session.scalars(stmt))

    def detail(self, company_id: uuid.UUID) -> CompanyDetail | None:
        company = self.session.scalars(
            select(Company)
            .where(Company.id == company_id)
            .options(selectinload(Company.domains), selectinload(Company.sources))
        ).first()
        if company is None:
            return None
        lead = self.session.scalars(select(Lead).where(Lead.company_id == company_id)).first()
        runs = list(
            self.session.scalars(
                select(ResearchRun)
                .where(ResearchRun.company_id == company_id)
                .order_by(ResearchRun.created_at.desc())
                .limit(20)
            )
        )
        entity_ids = [company.id] + ([lead.id] if lead else [])
        history = list(
            self.session.scalars(
                select(WorkflowEvent)
                .where(WorkflowEvent.entity_id.in_(entity_ids))
                .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id)
                .limit(50)
            )
        )
        contacts = list(
            self.session.scalars(
                select(Contact).where(Contact.company_id == company_id).order_by(Contact.kind)
            )
        )
        latest_audit = self.session.scalars(
            select(WebsiteAudit)
            .where(WebsiteAudit.company_id == company_id)
            .order_by(WebsiteAudit.fetched_at.desc())
            .limit(1)
        ).first()
        latest_run_id = runs[0].id if runs else None
        findings = (
            list(
                self.session.scalars(
                    select(ResearchFinding)
                    .where(ResearchFinding.research_run_id == latest_run_id)
                    .order_by(ResearchFinding.kind, ResearchFinding.key)
                )
            )
            if latest_run_id
            else []
        )
        opportunities = list(
            self.session.scalars(
                select(Opportunity)
                .where(Opportunity.company_id == company_id)
                .order_by(Opportunity.strength.desc(), Opportunity.service)
            )
        )
        latest_score = self.session.scalars(
            select(LeadScore)
            .where(LeadScore.company_id == company_id)
            .options(selectinload(LeadScore.components))
            .order_by(LeadScore.computed_at.desc())
            .limit(1)
        ).first()
        return CompanyDetail(
            company=company,
            lead=lead,
            research_runs=runs,
            history=history,
            contacts=contacts,
            latest_audit=latest_audit,
            findings=findings,
            opportunities=opportunities,
            latest_score=latest_score,
        )
