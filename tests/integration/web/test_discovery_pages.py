from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.domain.auth import Role
from app.infrastructure.database import Database
from app.infrastructure.database.models import Company, User
from tests.integration.web.conftest import login


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


def _csrf(client: TestClient) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/companies/new").text)
    assert match
    return match.group(1)


def _form(**kw: str) -> dict[str, str]:
    data = {
        "name": "Denov Savdo",
        "country": "UZ",
        "city": "Denov",
        "domain": "denovsavdo.uz",
        "phone": "90 123 45 67",
        "email": "info@denovsavdo.uz",
    }
    data.update(kw)
    return data


def test_new_form_is_routed_and_owner_only(web: TestClient, authed: TestClient) -> None:
    r = authed.get("/companies/new")
    assert r.status_code == 200 and 'name="name"' in r.text
    assert "+ Qo&#39;shish" in authed.get("/companies").text


def test_anonymous_and_viewer_blocked(web: TestClient, db: Database) -> None:
    assert web.get("/companies/new").status_code == 303
    with db.transaction() as s:
        s.add(
            User(
                username="viewer1",
                password_hash=hash_password("Viewer-Pass-2026!"),
                role=Role.VIEWER,
            )
        )
    login(web, username="viewer1", password="Viewer-Pass-2026!")
    assert web.get("/companies/new").status_code == 403
    assert web.get("/companies/import").status_code == 403
    assert "+ Qo&#39;shish" not in web.get("/companies").text


def test_create_then_detail_shows_contacts(authed: TestClient) -> None:
    r = authed.post("/companies/new", data={"csrf_token": _csrf(authed), **_form()})
    assert r.status_code == 303
    detail = authed.get(r.headers["location"]).text
    assert "+998901234567" in detail and "info@denovsavdo.uz" in detail and "manual" in detail


def test_duplicate_shows_link_and_allows_name_city_override(
    authed: TestClient, db: Database
) -> None:
    csrf = _csrf(authed)
    authed.post("/companies/new", data={"csrf_token": csrf, **_form()})
    hard = authed.post(
        "/companies/new", data={"csrf_token": csrf, **_form(name="Other", city="Termiz")}
    )
    assert (
        hard.status_code == 409
        and "Mavjudini ochish" in hard.text
        and "allow_duplicate" not in hard.text
    )
    soft = authed.post(
        "/companies/new", data={"csrf_token": csrf, **_form(domain="", phone="", email="")}
    )
    assert soft.status_code == 409 and 'name="allow_duplicate"' in soft.text
    forced = authed.post(
        "/companies/new",
        data={"csrf_token": csrf, **_form(domain="", phone="", email="", allow_duplicate="1")},
    )
    assert forced.status_code == 303
    with db.transaction() as s:
        assert len(s.scalars(select(Company)).all()) == 2


def test_invalid_input_keeps_form_values(authed: TestClient) -> None:
    r = authed.post("/companies/new", data={"csrf_token": _csrf(authed), **_form(phone="123")})
    assert r.status_code == 400 and "Xato:" in r.text and 'value="Denov Savdo"' in r.text


def test_create_requires_csrf(authed: TestClient) -> None:
    assert authed.post("/companies/new", data=_form()).status_code == 403


def test_csv_upload_dry_run_then_import(authed: TestClient, db: Database) -> None:
    csv_data = b"name,country,city,phone\nTermiz Mebel,UZ,Termiz,93 111 22 33\nBad,UZ,X,12\n"
    csrf = _csrf(authed)
    files = {"file": ("mebel.csv", csv_data, "text/csv")}
    preview = authed.post(
        "/companies/import", data={"csrf_token": csrf, "dry_run": "1"}, files=files
    )
    assert preview.status_code == 200
    assert "1 ta yangi · 0 ta dublikat · 1 ta xato" in preview.text
    assert "hech narsa saqlanmadi" in preview.text
    with db.transaction() as s:
        assert s.scalars(select(Company)).first() is None

    real = authed.post(
        "/companies/import",
        data={"csrf_token": csrf},
        files={"file": ("mebel.csv", csv_data, "text/csv")},
    )
    assert "1 ta yangi" in real.text and "hech narsa saqlanmadi" not in real.text
    with db.transaction() as s:
        assert s.scalars(select(Company.name)).all() == ["Termiz Mebel"]


def test_csv_bad_file_is_400(authed: TestClient) -> None:
    r = authed.post(
        "/companies/import",
        data={"csrf_token": _csrf(authed)},
        files={"file": ("x.csv", b"foo,bar\n1,2\n", "text/csv")},
    )
    assert r.status_code == 400 and "missing required" in r.text
