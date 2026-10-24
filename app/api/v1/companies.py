"""Read-only company API (session-authenticated). Writes arrive with M4."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_database
from app.application.companies import CompanyQueryService
from app.infrastructure.database import Database
from app.web.auth import CurrentUser, require_user
from app.web.companies import parse_company_query

router = APIRouter(prefix="/companies", tags=["companies"])


class CompanyItem(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    city: str | None
    industry: str | None
    research_state: str
    primary_domain: str | None
    lead_stage: str | None
    is_fixture: bool


class PageMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int


class CompanyListResponse(BaseModel):
    items: list[CompanyItem]
    meta: PageMeta


class SourceOut(BaseModel):
    source_type: str
    source_url: str | None
    retrieved_at: datetime
    is_fixture: bool


class CompanyDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    city: str | None
    industry: str | None
    research_state: str
    domains: list[str]
    sources: list[SourceOut]
    lead_stage: str | None
    created_at: datetime


@router.get("", response_model=CompanyListResponse)
def list_companies(
    request: Request,
    per_page: int = 20,
    _: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> CompanyListResponse:
    """Query params: q, country, state, sort (newest|oldest|name), page, per_page (≤100)."""
    query = parse_company_query(request, per_page=max(1, min(per_page, 100)))
    with database.transaction() as session:
        page = CompanyQueryService(session).search(query)
    return CompanyListResponse(
        items=[
            CompanyItem(
                id=row.id,
                name=row.name,
                country=row.country,
                city=row.city,
                industry=row.industry,
                research_state=row.research_state.value,
                primary_domain=row.primary_domain,
                lead_stage=row.lead_stage,
                is_fixture=row.is_fixture,
            )
            for row in page.items
        ],
        meta=PageMeta(page=page.page, per_page=page.per_page, total=page.total, pages=page.pages),
    )


@router.get("/{company_id}", response_model=CompanyDetailResponse)
def get_company(
    company_id: uuid.UUID,
    _: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> CompanyDetailResponse:
    with database.transaction() as session:
        detail = CompanyQueryService(session).detail(company_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Company not found")
        c = detail.company
        return CompanyDetailResponse(
            id=c.id,
            name=c.name,
            country=c.country,
            city=c.city,
            industry=c.industry,
            research_state=c.research_state.value,
            domains=[d.domain for d in c.domains],
            sources=[
                SourceOut(
                    source_type=s.source_type,
                    source_url=s.source_url,
                    retrieved_at=s.retrieved_at,
                    is_fixture=s.is_fixture,
                )
                for s in c.sources
            ],
            lead_stage=detail.lead.stage.value if detail.lead else None,
            created_at=c.created_at,
        )
