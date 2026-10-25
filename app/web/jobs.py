"""Job monitoring and error view (M10): queue list, job drill-down, owner retry/cancel."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from app.api.deps import get_database
from app.application.automation import JobAdminService, JobFilter, cron_view, latest_runner_run
from app.domain.actors import Actor
from app.domain.agents import AgentModule
from app.domain.automation import error_category
from app.domain.errors import DomainError
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import Job
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_user
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)
STATUSES = [
    JobStatus.FAILED,
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.SUCCEEDED,
    JobStatus.CANCELLED,
]


def _parse_id(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


@router.get("/jobs", response_class=HTMLResponse)
def job_list(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    params = request.query_params
    try:
        status = JobStatus(params.get("status", "")) if params.get("status") else None
    except ValueError:
        status = None
    module = params.get("module") or None
    if module not in {m.value for m in AgentModule}:
        module = None
    try:
        page = max(1, int(params.get("page", "1")))
    except ValueError:
        page = 1
    with database.transaction() as session:
        service = JobAdminService(session)
        jobs, total = service.search(JobFilter(status=status, module=module, page=page))
        counts = service.counts()
        cron = cron_view(session)
        last_run = latest_runner_run(session)
        context = layout_context(session, user)
    pages = max(1, -(-total // JobAdminService.PAGE_SIZE))
    context.update(
        {
            "jobs": jobs,
            "total": total,
            "page": min(page, pages),
            "pages": pages,
            "status": status,
            "module": module,
            "statuses": STATUSES,
            "modules": [m.value for m in AgentModule],
            "counts": {s.value: n for s, n in counts.items()},
            "cron": cron,
            "last_run": last_run,
            "category": error_category,
        }
    )
    return render(request, "jobs/list.html", context)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(
    request: Request,
    job_id: str,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    jid = _parse_id(job_id)
    with database.transaction() as session:
        context = layout_context(session, user)
        service = JobAdminService(session)
        job = session.get(Job, jid) if jid else None
        if job is None or jid is None:
            context["title_key"] = "error.not_found"
            return render(request, "error.html", context, status=404)
        runs = service.runs(jid)
    context.update(
        {
            "job": job,
            "runs": runs,
            "done": request.query_params.get("done"),
            "category": error_category,
        }
    )
    return render(request, "jobs/detail.html", context)


@router.post("/jobs/{job_id}/{action}")
def job_action(
    job_id: str,
    action: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    if action not in ("retry", "cancel"):
        raise DomainError("unknown action")
    jid = _parse_id(job_id)
    actor = Actor.user(str(user.id))
    with database.transaction() as session:
        if jid is None or session.get(Job, jid) is None:
            return PlainTextResponse("Not found", status_code=404)
        service = JobAdminService(session)
        if action == "retry":
            service.retry(jid, actor)
        else:
            service.cancel(jid, actor)
    return RedirectResponse(f"/jobs/{jid}?done={action}", status_code=303)
