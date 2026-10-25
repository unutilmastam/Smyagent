from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.infrastructure.database import Database
from app.infrastructure.database.models import DiscoveryTarget, Job
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from tests.integration.web.conftest import login


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


def _csrf(client: TestClient) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/discovery").text)
    assert match
    return match.group(1)


def test_page_requires_owner(web: TestClient) -> None:
    assert web.get("/discovery").status_code == 303


def test_add_toggle_and_run_now(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed)
    r = authed.post(
        "/discovery/targets",
        data={
            "csrf_token": csrf,
            "country": "UZ",
            "city": "Sherobod",
            "categories": ["food", "auto"],
        },
    )
    assert r.status_code == 303
    page = authed.get("/discovery").text
    assert "Sherobod, UZ" in page and "Kafe va restoranlar" in page and "OpenStreetMap" in page
    with db.transaction() as s:
        target_id = s.scalars(select(DiscoveryTarget.id)).one()

    run = authed.post(f"/discovery/targets/{target_id}/run", data={"csrf_token": csrf})
    assert run.headers["location"] == "/discovery?queued=2"
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(Job)) == 2

    authed.post(f"/discovery/targets/{target_id}/toggle", data={"csrf_token": csrf})
    with db.transaction() as s:
        assert s.scalars(select(DiscoveryTarget.enabled)).one() is False


def test_invalid_target_is_rejected(authed: TestClient, db: Database) -> None:
    csrf = _csrf(authed)
    r = authed.post(
        "/discovery/targets", data={"csrf_token": csrf, "country": "UZ", "city": "Denov"}
    )
    assert "error=" in r.headers["location"]
    with db.transaction() as s:
        assert s.scalars(select(DiscoveryTarget)).first() is None


def test_requires_csrf(authed: TestClient) -> None:
    r = authed.post(
        "/discovery/targets", data={"country": "UZ", "city": "Denov", "categories": ["food"]}
    )
    assert r.status_code == 403


def test_osm_attribution_on_company(authed: TestClient, db: Database) -> None:
    with db.transaction() as s:
        cid = (
            CompanyRepository(s)
            .add(
                NewCompany(
                    name="Denov Mebel",
                    country="UZ",
                    source_type="osm",
                    source_url="https://www.openstreetmap.org/node/1",
                )
            )
            .id
        )
    assert "OpenStreetMap hissadorlari" in authed.get(f"/companies/{cid}").text
