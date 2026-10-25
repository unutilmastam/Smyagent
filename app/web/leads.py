"""Lead list (sorted by latest score) and scoring settings (M6)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from app.api.deps import get_database
from app.domain.actors import Actor
from app.domain.leads import LeadStage
from app.domain.scoring import Component
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Company,
    Lead,
    LeadScore,
    Opportunity,
    ScoringSettings,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.workflow import AuditLogRepository
from app.jobs.tasks.scoring import load_settings
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_owner, require_user
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)
PAGE_SIZE = 50


@router.get("/leads", response_class=HTMLResponse)
def lead_list(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    stage_param = request.query_params.get("stage") or ""
    try:
        stage = LeadStage(stage_param) if stage_param else None
    except ValueError:
        stage = None
    with database.transaction() as session:
        latest = (
            select(LeadScore.company_id, func.max(LeadScore.computed_at).label("at"))
            .group_by(LeadScore.company_id)
            .subquery()
        )
        stmt = (
            select(Lead, Company, LeadScore.total)
            .join(Company, Company.id == Lead.company_id)
            .outerjoin(latest, latest.c.company_id == Lead.company_id)
            .outerjoin(
                LeadScore,
                (LeadScore.company_id == Lead.company_id) & (LeadScore.computed_at == latest.c.at),
            )
        )
        if stage is not None:
            stmt = stmt.where(Lead.stage == stage)
        rows = session.execute(
            stmt.order_by(LeadScore.total.desc(), Lead.stage_changed_at.desc()).limit(PAGE_SIZE)
        ).all()
        best: dict[object, str] = {}
        for opp in session.scalars(
            select(Opportunity)
            .where(Opportunity.company_id.in_([c.id for _, c, _ in rows]))
            .order_by(Opportunity.strength.desc())
        ):
            best.setdefault(opp.company_id, opp.service)
        counts = dict(
            session.execute(select(Lead.stage, func.count()).group_by(Lead.stage)).tuples().all()
        )
        context = layout_context(session, user)
    context.update(
        {
            "rows": [(lead, company, total, best.get(company.id)) for lead, company, total in rows],
            "stage": stage,
            "counts": {s.value: n for s, n in counts.items()},
            "stages": [
                LeadStage.CANDIDATE,
                LeadStage.QUALIFIED,
                LeadStage.AWAITING_APPROVAL,
                LeadStage.APPROVED,
                LeadStage.DISQUALIFIED,
            ],
        }
    )
    return render(request, "leads.html", context)


@router.get("/settings/scoring", response_class=HTMLResponse)
def scoring_settings(
    request: Request,
    user: CurrentUser = Depends(require_owner),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    with database.transaction() as session:
        weights, threshold = load_settings(session)
        context = layout_context(session, user)
    context.update(
        {
            "weights": {c.value: w for c, w in weights.items()},
            "threshold": threshold,
            "components": list(Component),
            "saved": request.query_params.get("saved") == "1",
        }
    )
    return render(request, "settings_scoring.html", context)


@router.post("/settings/scoring")
async def save_scoring_settings(
    request: Request,
    threshold: Annotated[int, Form(ge=0, le=100)],
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    form = await request.form()
    weights: dict[str, float] = {}
    for component in Component:
        raw = form.get(f"w_{component.value}")
        try:
            weights[component.value] = max(0.0, min(10.0, float(str(raw))))
        except (TypeError, ValueError):
            continue
    with database.transaction() as session:
        row = session.get(ScoringSettings, "default") or ScoringSettings(key="default")
        row.weights = weights
        row.qualify_threshold = threshold
        row.updated_at = utcnow()
        row.updated_by = f"user:{user.id}"
        session.add(row)
        AuditLogRepository(session).add(
            actor=Actor.user(str(user.id)),
            action="settings.scoring",
            details={"weights": weights, "threshold": threshold},
        )
    return RedirectResponse("/settings/scoring?saved=1", status_code=303)
