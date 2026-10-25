"""Job monitoring pages, owner retry/cancel and cron warnings (M10)."""

from __future__ import annotations

import re
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.domain.auth import Role
from app.domain.automation import RunnerStatus
from app.domain.jobs import JobStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import AuditLog, Job, RunnerRun, User
from app.infrastructure.database.types import utcnow
from tests.integration.web.conftest import login


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def _job(db: Database, status: JobStatus, error: str | None = None) -> uuid.UUID:
    with db.transaction() as s:
        job = Job(
            job_type="research.audit",
            agent_module="research_audit",
            status=status,
            payload={"company_id": "c-1"},
            attempts=3 if status is JobStatus.FAILED else 0,
            last_error=error,
            finished_at=utcnow() if status is JobStatus.FAILED else None,
        )
        s.add(job)
        s.flush()
        return job.id


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


def test_jobs_require_login(web: TestClient) -> None:
    assert web.get("/jobs").status_code in (302, 303)


def test_list_filters_and_cron_never_warning(authed: TestClient, db: Database) -> None:
    failed = _job(db, JobStatus.FAILED, "dns: lookup failed after 3 tries")
    _job(db, JobStatus.QUEUED)
    page = authed.get("/jobs")
    assert page.status_code == 200 and "cron" in page.text.lower()
    assert "Cron Jobs" in page.text  # never ran: setup hint
    only_failed = authed.get("/jobs?status=FAILED").text
    assert str(failed) in only_failed and only_failed.count('class="company-item"') == 1
    assert "dns" in only_failed
    # Unknown filters are ignored, not errors.
    assert authed.get("/jobs?status=NOPE&module=x&page=abc").status_code == 200


def test_cron_late_warning_on_home_and_control(authed: TestClient, db: Database) -> None:
    with db.transaction() as s:
        s.add(
            RunnerRun(
                worker_id="w",
                status=RunnerStatus.OK,
                started_at=utcnow() - timedelta(minutes=40),
            )
        )
    for path in ("/", "/control", "/jobs"):
        assert "40" in authed.get(path).text and "alert-error" in authed.get(path).text


def test_detail_retry_and_cancel(authed: TestClient, db: Database) -> None:
    failed = _job(db, JobStatus.FAILED, "TimeoutError")
    detail = authed.get(f"/jobs/{failed}")
    assert detail.status_code == 200 and "TimeoutError" in detail.text and "c-1" in detail.text
    csrf = _csrf(detail.text)
    r = authed.post(f"/jobs/{failed}/retry", data={"csrf_token": csrf})
    assert r.status_code == 303 and r.headers["location"] == f"/jobs/{failed}?done=retry"
    r = authed.post(f"/jobs/{failed}/cancel", data={"csrf_token": csrf})
    assert r.status_code == 303
    with db.transaction() as s:
        job = s.get(Job, failed)
        assert job is not None and job.status is JobStatus.CANCELLED
        actions = s.scalars(select(AuditLog.action).where(AuditLog.action.like("job.%"))).all()
    assert sorted(actions) == ["job.cancel", "job.retry"]
    # Invalid action / state / id
    assert authed.post(f"/jobs/{failed}/cancel", data={"csrf_token": csrf}).status_code == 400
    assert authed.post(f"/jobs/{failed}/delete", data={"csrf_token": csrf}).status_code == 400
    assert authed.get("/jobs/not-a-uuid").status_code == 404
    assert authed.post(f"/jobs/{uuid.uuid4()}/retry", data={"csrf_token": csrf}).status_code == 404
    assert authed.get(f"/jobs/{uuid.uuid4()}").status_code == 404


def test_retry_requires_csrf(authed: TestClient, db: Database) -> None:
    failed = _job(db, JobStatus.FAILED, "x")
    assert authed.post(f"/jobs/{failed}/retry", data={}).status_code == 403
    with db.transaction() as s:
        assert s.get(Job, failed).status is JobStatus.FAILED  # type: ignore[union-attr]


def test_viewer_sees_but_cannot_retry(web: TestClient, db: Database) -> None:
    with db.transaction() as s:
        s.add(
            User(
                username="viewer1",
                password_hash=hash_password("Viewer-Pass-2026!"),
                role=Role.VIEWER,
            )
        )
    failed = _job(db, JobStatus.FAILED, "x")
    assert login(web, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    page = web.get(f"/jobs/{failed}")
    assert page.status_code == 200 and "/retry" not in page.text
    r = web.post(f"/jobs/{failed}/retry", data={"csrf_token": _csrf(web.get("/control").text)})
    assert r.status_code == 403
