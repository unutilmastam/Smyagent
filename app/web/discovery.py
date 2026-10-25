"""Manual company entry and CSV import pages (M4). Owner only, CSRF-protected."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.api.deps import get_database
from app.application.csv_import import MAX_BYTES, CsvFormatError, import_csv
from app.application.discovery import DiscoveryService, IntakeStatus
from app.domain.actors import Actor
from app.infrastructure.database import Database
from app.infrastructure.repositories.companies import NewCompany
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_owner
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)

FORM_FIELDS = (
    "name",
    "country",
    "city",
    "industry",
    "domain",
    "phone",
    "email",
    "telegram",
    "source_url",
    "notes",
)


def _split(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split("|") if v.strip())


def _page(
    request: Request,
    database: Database,
    user: CurrentUser,
    name: str,
    extra: dict[str, object],
    status: int = 200,
) -> Response:
    with database.transaction() as session:
        context = layout_context(session, user)
    context.update(extra)
    return render(request, name, context, status=status)


@router.get("/companies/new", response_class=HTMLResponse)
def new_company_form(
    request: Request,
    user: CurrentUser = Depends(require_owner),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    form = dict.fromkeys(FORM_FIELDS, "")
    form["country"] = "UZ"
    return _page(request, database, user, "companies/new.html", {"form": form, "result": None})


@router.post("/companies/new")
def create_company(
    request: Request,
    name: Annotated[str, Form(max_length=255)],
    country: Annotated[str, Form(max_length=8)],
    city: Annotated[str, Form(max_length=191)] = "",
    industry: Annotated[str, Form(max_length=191)] = "",
    domain: Annotated[str, Form(max_length=500)] = "",
    phone: Annotated[str, Form(max_length=200)] = "",
    email: Annotated[str, Form(max_length=300)] = "",
    telegram: Annotated[str, Form(max_length=200)] = "",
    source_url: Annotated[str, Form(max_length=2000)] = "",
    notes: Annotated[str, Form(max_length=2000)] = "",
    allow_duplicate: Annotated[str, Form(max_length=1)] = "",
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    data = NewCompany(
        name=name,
        country=country,
        city=city or None,
        industry=industry or None,
        domains=_split(domain),
        phones=_split(phone),
        emails=_split(email),
        telegrams=_split(telegram),
        source_type="manual",
        source_url=source_url.strip() or None,
        notes=notes or None,
        allow_name_city_duplicate=allow_duplicate == "1",
    )
    with database.transaction() as session:
        result = DiscoveryService(session).ingest(data, Actor.user(str(user.id)))
    if result.status is IntakeStatus.CREATED:
        return RedirectResponse(f"/companies/{result.company_id}", status_code=303)
    form = {
        "name": name,
        "country": country,
        "city": city,
        "industry": industry,
        "domain": domain,
        "phone": phone,
        "email": email,
        "telegram": telegram,
        "source_url": source_url,
        "notes": notes,
    }
    status = 409 if result.status is IntakeStatus.DUPLICATE else 400
    return _page(
        request, database, user, "companies/new.html", {"form": form, "result": result}, status
    )


@router.get("/companies/import", response_class=HTMLResponse)
def import_form(
    request: Request,
    user: CurrentUser = Depends(require_owner),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    return _page(request, database, user, "companies/import.html", {"report": None})


@router.post("/companies/import")
async def import_upload(
    request: Request,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[str, Form(max_length=1)] = "",
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    data = await file.read(MAX_BYTES + 1)
    try:
        with database.transaction() as session:
            report = import_csv(
                session,
                data,
                filename=file.filename or "upload.csv",
                actor=Actor.user(str(user.id)),
                dry_run=dry_run == "1",
            )
    except CsvFormatError as exc:
        return _page(
            request,
            database,
            user,
            "companies/import.html",
            {"report": None, "error": str(exc)},
            status=400,
        )
    return _page(request, database, user, "companies/import.html", {"report": report})
