"""Offers: list, detail with evidence and gate verdict, owner approve/reject/edit, export (M7)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_database
from app.application.proposals import MAX_BODY, MAX_TITLE, ProposalService, export_markdown
from app.domain.actors import Actor
from app.domain.errors import DomainError
from app.domain.proposals import ProposalStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    ApprovalRequest,
    Company,
    Proposal,
    ResearchFinding,
)
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_user
from app.web.i18n import translator
from app.web.layout import layout_context
from app.web.templating import render, request_language

router = APIRouter(include_in_schema=False)
PAGE_SIZE = 50
OPEN_STATUSES = (ProposalStatus.AWAITING_APPROVAL, ProposalStatus.NEEDS_EDIT)


def _parse_id(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


@router.get("/proposals", response_class=HTMLResponse)
def proposal_list(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    raw = request.query_params.get("status") or ""
    try:
        status = ProposalStatus(raw) if raw else None
    except ValueError:
        status = None
    with database.transaction() as session:
        stmt = select(Proposal, Company).join(Company, Company.id == Proposal.company_id)
        if status is not None:
            stmt = stmt.where(Proposal.status == status)
        rows = session.execute(
            stmt.options(selectinload(Proposal.versions))
            .order_by(Proposal.updated_at.desc())
            .limit(PAGE_SIZE)
        ).all()
        counts = dict(
            session.execute(select(Proposal.status, func.count()).group_by(Proposal.status))
            .tuples()
            .all()
        )
        context = layout_context(session, user)
    context.update(
        {
            "rows": [(p, c, p.versions[0] if p.versions else None) for p, c in rows],
            "status": status,
            "statuses": list(ProposalStatus),
            "counts": {s.value: n for s, n in counts.items()},
        }
    )
    return render(request, "proposals/list.html", context)


def _detail(session: Session, proposal_id: uuid.UUID) -> dict[str, Any] | None:
    proposal = session.get(Proposal, proposal_id, options=[selectinload(Proposal.versions)])
    if proposal is None:
        return None
    company = session.get(Company, proposal.company_id)
    version = next(v for v in proposal.versions if v.number == proposal.current_version)
    ids = [uuid.UUID(i) for i in version.finding_ids]
    findings = (
        list(
            session.scalars(
                select(ResearchFinding)
                .where(ResearchFinding.id.in_(ids))
                .order_by(ResearchFinding.kind, ResearchFinding.key)
            )
        )
        if ids
        else []
    )
    approvals = list(
        session.scalars(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.entity_type == "proposal",
                ApprovalRequest.entity_id == proposal.id,
            )
            .order_by(ApprovalRequest.created_at.desc())
            .limit(20)
        )
    )
    return {
        "proposal": proposal,
        "company": company,
        "version": version,
        "findings": findings,
        "approvals": approvals,
        "max_title": MAX_TITLE,
        "max_body": MAX_BODY,
    }


@router.get("/proposals/{proposal_id}", response_class=HTMLResponse)
def proposal_detail(
    request: Request,
    proposal_id: str,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    parsed = _parse_id(proposal_id)
    with database.transaction() as session:
        data = _detail(session, parsed) if parsed else None
        context = layout_context(session, user)
        if data is None:
            context["title_key"] = "error.not_found"
            return render(request, "error.html", context, status=404)
        context.update(data)
        context["done"] = request.query_params.get("done")
        return render(request, "proposals/detail.html", context)


@router.get("/proposals/{proposal_id}/export.md")
def proposal_export(
    request: Request,
    proposal_id: str,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    parsed = _parse_id(proposal_id)
    with database.transaction() as session:
        data = _detail(session, parsed) if parsed else None
        if data is None or data["company"] is None:
            return PlainTextResponse("Not found", status_code=404)
        t = translator(request_language(request))
        text = export_markdown(data["proposal"], data["company"], data["findings"], t)
    return PlainTextResponse(
        text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="proposal-{parsed}.md"'},
    )


def _owner_action(
    request: Request,
    proposal_id: str,
    user: CurrentUser,
    database: Database,
    action: str,
    **form: str,
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    parsed = _parse_id(proposal_id)
    if parsed is None:
        return PlainTextResponse("Not found", status_code=404)
    actor = Actor.user(str(user.id))
    error: str | None = None
    try:
        with database.transaction() as session:
            service = ProposalService(session)
            if action == "approve":
                service.approve(parsed, actor)
            elif action == "reject":
                service.reject(parsed, actor, form.get("reason", ""))
            else:
                service.edit(parsed, actor, title=form["title"], body=form["body"])
    except DomainError as exc:
        error = str(exc)[:200]
    if error is None:
        return RedirectResponse(f"/proposals/{parsed}?done={action}", status_code=303)
    with database.transaction() as session:
        data = _detail(session, parsed)
        context = layout_context(session, user)
        if data is None:
            return PlainTextResponse("Not found", status_code=404)
        context.update(data)
        context["error"] = error
        return render(request, "proposals/detail.html", context, status=409)


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(
    request: Request,
    proposal_id: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    return _owner_action(request, proposal_id, user, database, "approve")


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    request: Request,
    proposal_id: str,
    reason: Annotated[str, Form(max_length=300)] = "",
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    return _owner_action(request, proposal_id, user, database, "reject", reason=reason)


@router.post("/proposals/{proposal_id}/edit")
def edit_proposal(
    request: Request,
    proposal_id: str,
    title: Annotated[str, Form(max_length=MAX_TITLE)],
    body: Annotated[str, Form(max_length=MAX_BODY)],
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    return _owner_action(request, proposal_id, user, database, "edit", title=title, body=body)
