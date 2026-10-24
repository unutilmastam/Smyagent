"""Company list (search/filter/sort/pagination, HTMX partials) and detail pages."""

from __future__ import annotations

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from app.api.deps import get_database
from app.application.companies import (
    DEFAULT_PAGE_SIZE,
    CompanyQuery,
    CompanyQueryService,
    CompanySort,
)
from app.domain.companies import ResearchState, normalize_country
from app.domain.errors import DomainError
from app.infrastructure.database import Database
from app.web.auth import CurrentUser, require_user
from app.web.layout import layout_context
from app.web.templating import is_htmx_partial, render

router = APIRouter(include_in_schema=False)


def parse_company_query(request: Request, *, per_page: int = DEFAULT_PAGE_SIZE) -> CompanyQuery:
    """Lenient parsing: bad filter values are ignored instead of failing the page."""
    params = request.query_params
    country: str | None = None
    try:
        country = normalize_country(params["country"]) if params.get("country") else None
    except DomainError:
        country = None
    try:
        state = ResearchState(params["state"]) if params.get("state") else None
    except ValueError:
        state = None
    try:
        sort = CompanySort(params.get("sort") or CompanySort.NEWEST.value)
    except ValueError:
        sort = CompanySort.NEWEST
    try:
        page = max(1, min(int(params.get("page") or 1), 100_000))
    except ValueError:
        page = 1
    return CompanyQuery(
        q=(params.get("q") or "")[:100],
        country=country,
        state=state,
        sort=sort,
        page=page,
        per_page=per_page,
    )


def _page_url(query: CompanyQuery, page: int) -> str:
    params = {
        "q": query.q,
        "country": query.country or "",
        "state": query.state.value if query.state else "",
        "sort": query.sort.value,
        "page": str(page),
    }
    return "/companies?" + urlencode({k: v for k, v in params.items() if v})


@router.get("/companies", response_class=HTMLResponse)
def company_list(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    query = parse_company_query(request)
    with database.transaction() as session:
        service = CompanyQueryService(session)
        page = service.search(query)
        context: dict[str, object] = {
            "query": query,
            "page": page,
            "page_url": lambda n: _page_url(query, n),
        }
        if is_htmx_partial(request):
            return render(request, "companies/_results.html", context)
        context.update(layout_context(session, user))
        context.update(
            {
                "countries": service.countries(),
                "states": list(ResearchState),
                "sorts": list(CompanySort),
            }
        )
        return render(request, "companies/list.html", context)


@router.get("/companies/{company_id}", response_class=HTMLResponse)
def company_detail(
    request: Request,
    company_id: str,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    try:
        parsed_id: uuid.UUID | None = uuid.UUID(company_id)
    except ValueError:
        parsed_id = None
    with database.transaction() as session:
        detail = CompanyQueryService(session).detail(parsed_id) if parsed_id else None
        context = layout_context(session, user)
        if detail is None:
            context["title_key"] = "error.not_found"
            return render(request, "error.html", context, status=404)
        context["detail"] = detail
        return render(request, "companies/detail.html", context)
