"""Analytics page (M11): funnel, outreach, agents, AI budget and cost."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from app.api.deps import get_database
from app.application.analytics import PERIODS, AnalyticsService
from app.core.config import Settings, get_settings
from app.infrastructure.database import Database
from app.web.auth import CurrentUser, require_user
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    try:
        days = int(request.query_params.get("days", "7"))
    except ValueError:
        days = 7
    with database.transaction() as session:
        report = AnalyticsService(session, settings).report(days)
        context = layout_context(session, user)
    context.update({"r": report, "periods": PERIODS})
    return render(request, "analytics.html", context)
