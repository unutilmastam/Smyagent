"""Proposal pages: list, detail, owner approve/reject/edit, export, permissions (M7)."""

from __future__ import annotations

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.domain.auth import Role
from app.infrastructure.database import Database
from app.infrastructure.database.models import Lead, Proposal, User
from tests.integration.proposal_helpers import awaiting_proposal
from tests.integration.web.conftest import login


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


@pytest.fixture
def pid(db: Database) -> uuid.UUID:
    return awaiting_proposal(db)


def _state(db: Database, pid: uuid.UUID) -> tuple[str, str]:
    with db.transaction() as s:
        p = s.get(Proposal, pid)
        assert p is not None
        lead = s.get(Lead, p.lead_id)
        assert lead is not None
        return p.status.value, lead.stage.value


def test_pages_require_login(web: TestClient, pid: uuid.UUID) -> None:
    for url in ("/proposals", f"/proposals/{pid}", f"/proposals/{pid}/export.md"):
        assert web.get(url).status_code in (302, 303)


def test_list_and_home_counter(authed: TestClient, pid: uuid.UUID) -> None:
    html = authed.get("/proposals").text
    assert "Lazzat Oshxonasi" in html and "Tasdiq kutilmoqda" in html
    assert "Lazzat" in authed.get("/proposals?status=AWAITING_APPROVAL").text
    assert "Lazzat" not in authed.get("/proposals?status=APPROVED").text
    assert authed.get("/proposals?status=BOGUS").status_code == 200
    home = authed.get("/").text
    assert 'href="/proposals?status=AWAITING_APPROVAL"><span class="stat-value">1<' in home


def test_detail_shows_text_gate_and_evidence(authed: TestClient, pid: uuid.UUID) -> None:
    html = authed.get(f"/proposals/{pid}").text
    assert "Men Mustafo" in html and "kerak emas" in html
    assert "Toza" in html  # gate verdict
    assert "openstreetmap.org/node/1" in html  # evidence source
    assert "Saytda qaysi xizmat" in html  # open question for the owner
    assert 'action="/proposals/' in html and "Tasdiqlayman" in html


def test_not_found(authed: TestClient) -> None:
    assert authed.get("/proposals/nope").status_code == 404
    assert authed.get(f"/proposals/{uuid.uuid4()}").status_code == 404


def test_approve_from_dashboard(authed: TestClient, db: Database, pid: uuid.UUID) -> None:
    csrf = _csrf(authed.get(f"/proposals/{pid}").text)
    assert authed.post(f"/proposals/{pid}/approve").status_code == 403  # no CSRF token
    r = authed.post(f"/proposals/{pid}/approve", data={"csrf_token": csrf})
    assert r.status_code == 303 and r.headers["location"].endswith("done=approve")
    assert _state(db, pid) == ("APPROVED", "APPROVED")
    again = authed.post(f"/proposals/{pid}/approve", data={"csrf_token": csrf})
    assert again.status_code == 409 and "Bajarilmadi" in again.text


def test_reject_from_dashboard(authed: TestClient, db: Database, pid: uuid.UUID) -> None:
    csrf = _csrf(authed.get(f"/proposals/{pid}").text)
    r = authed.post(f"/proposals/{pid}/reject", data={"csrf_token": csrf, "reason": "kichik"})
    assert r.status_code == 303
    assert _state(db, pid) == ("REJECTED", "DISQUALIFIED")


def test_edit_with_price_shows_gate_issue(authed: TestClient, db: Database, pid: uuid.UUID) -> None:
    page = authed.get(f"/proposals/{pid}").text
    csrf = _csrf(page)
    with db.transaction() as s:
        body = s.get(Proposal, pid).versions[0].body  # type: ignore[union-attr]
    r = authed.post(
        f"/proposals/{pid}/edit",
        data={"csrf_token": csrf, "title": "Taklif", "body": body + "\nNarxi 100$"},
    )
    assert r.status_code == 303
    html = authed.get(f"/proposals/{pid}").text
    assert "Narx, summa" in html and "Tahrir kerak" in html and "v2" in html
    assert "Tasdiqlayman</button>" not in html  # approval hidden until fixed
    assert _state(db, pid) == ("NEEDS_EDIT", "PROPOSAL_DRAFTED")


def test_export_markdown(authed: TestClient, pid: uuid.UUID) -> None:
    r = authed.get(f"/proposals/{pid}/export.md")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown")
    assert "attachment" in r.headers["content-disposition"]
    text = r.text
    assert text.startswith("# Lazzat Oshxonasi uchun taklif")
    assert "## Evidence" in text and "openstreetmap.org/node/1" in text
    assert "## Open questions" in text


def test_viewer_can_read_but_not_decide(web: TestClient, db: Database, pid: uuid.UUID) -> None:
    with db.transaction() as s:
        s.add(
            User(
                username="viewer1",
                password_hash=hash_password("Viewer-Pass-2026!"),
                role=Role.VIEWER,
            )
        )
    assert login(web, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    html = web.get(f"/proposals/{pid}").text
    assert "Men Mustafo" in html and "Tasdiqlayman" not in html
    csrf = _csrf(web.get("/").text)
    for action in ("approve", "reject"):
        assert web.post(f"/proposals/{pid}/{action}", data={"csrf_token": csrf}).status_code == 403
    assert _state(db, pid) == ("AWAITING_APPROVAL", "AWAITING_APPROVAL")


def test_company_page_links_to_proposal(authed: TestClient, db: Database, pid: uuid.UUID) -> None:
    with db.transaction() as s:
        company_id = s.get(Proposal, pid).company_id  # type: ignore[union-attr]
    html = authed.get(f"/companies/{company_id}").text
    assert f'href="/proposals/{pid}"' in html


def test_no_inline_script_or_style(authed: TestClient, pid: uuid.UUID) -> None:
    for url in ("/proposals", f"/proposals/{pid}"):
        html = authed.get(url).text
        assert "<script>" not in html and "style=" not in html
