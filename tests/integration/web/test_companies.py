from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application.workflow import WorkflowService
from app.domain.actors import Actor
from app.domain.companies import ResearchState
from app.domain.leads import LeadStage
from app.infrastructure.database import Database
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.web.i18n import missing_keys
from app.web.pwa import MANIFEST, SHELL_ASSETS
from app.web.templating import STATIC_DIR
from tests.integration.web.conftest import login

XSS = "<script>alert(1)</script> Evil"


@pytest.fixture
def companies(db: Database) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    with db.transaction() as s:
        repo = CompanyRepository(s)
        ids["denov"] = repo.add(
            NewCompany(
                name="Denov Savdo MChJ",
                country="UZ",
                city="Denov",
                domains=("denovsavdo.uz",),
                source_type="csv",
            )
        ).id
        ids["almaty"] = repo.add(
            NewCompany(
                name="Almaty Logistics", country="KZ", city="Almaty", domains=("almaty-log.kz",)
            )
        ).id
        ids["fixture"] = repo.add(
            NewCompany(
                name="Fixture Firm",
                country="UZ",
                city="Termiz",
                source_type="fixture",
                is_fixture=True,
            )
        ).id
        ids["xss"] = repo.add(NewCompany(name=XSS, country="UZ", city="Qarshi")).id
        ids["percent"] = repo.add(NewCompany(name="100% Sifat", country="UZ", city="Buxoro")).id
        wf = WorkflowService(s)
        wf.transition_company(ids["denov"], ResearchState.RESEARCH_PENDING, Actor.system("cron"))
        lead = wf.create_lead(ids["denov"], Actor.user("owner"))
        wf.transition_lead(lead.id, LeadStage.QUALIFIED, Actor.agent("opportunity_scoring"))
    return ids


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


def _names(html: str) -> list[str]:
    return re.findall(r'class="company-name">([^<]*)<', html)


def test_list_requires_login(web: TestClient) -> None:
    r = web.get("/companies")
    assert r.status_code == 303 and r.headers["location"].startswith("/login?next=/companies")


def test_list_shows_all_with_total(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    r = authed.get("/companies")
    assert r.status_code == 200
    assert "Jami: 5" in r.text
    assert len(_names(r.text)) == 5
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("q", "expected"),
    [("denov", ["Denov Savdo MChJ"]), ("ALMATY-LOG", ["Almaty Logistics"]), ("zzz", [])],
)
def test_search_by_name_and_domain(
    authed: TestClient, companies: dict[str, uuid.UUID], q: str, expected: list[str]
) -> None:
    assert _names(authed.get("/companies", params={"q": q}).text) == expected


def test_like_wildcards_are_literal(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    assert _names(authed.get("/companies", params={"q": "100%"}).text) == ["100% Sifat"]
    assert _names(authed.get("/companies", params={"q": "_"}).text) == []


def test_filters_and_sort(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    assert _names(authed.get("/companies", params={"country": "kz"}).text) == ["Almaty Logistics"]
    pending = authed.get("/companies", params={"state": "RESEARCH_PENDING"}).text
    assert _names(pending) == ["Denov Savdo MChJ"]
    names = _names(authed.get("/companies", params={"sort": "name"}).text)
    plain = [n for n in names if not n.startswith("&lt;")]
    assert plain == ["100% Sifat", "Almaty Logistics", "Denov Savdo MChJ", "Fixture Firm"]


def test_invalid_filters_are_ignored(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    r = authed.get(
        "/companies", params={"state": "BOGUS", "country": "UZB", "page": "x", "sort": "?"}
    )
    assert r.status_code == 200 and "Jami: 5" in r.text


def test_pagination(authed: TestClient, db: Database) -> None:
    with db.transaction() as s:
        repo = CompanyRepository(s)
        for i in range(25):
            repo.add(NewCompany(name=f"Firm {i:02d}", country="UZ", city=f"City {i}"))
    page2 = authed.get("/companies", params={"page": 2, "sort": "name"}).text
    assert len(_names(page2)) == 5
    assert "2 / 2" in page2
    assert "page=1" in page2  # previous link keeps filters/sort
    assert "sort=name" in page2


def test_htmx_returns_fragment(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    r = authed.get("/companies", params={"q": "denov"}, headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<html" not in r.text and "Denov Savdo" in r.text


def test_output_is_escaped(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    for path in ("/companies", f"/companies/{companies['xss']}"):
        html = authed.get(path).text
        assert XSS not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_no_inline_scripts_or_styles(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    for path in ("/", "/companies", f"/companies/{companies['denov']}", "/login"):
        html = authed.get(path).text
        assert not re.search(r"<script(?![^>]*\bsrc=)", html), path
        assert " style=" not in html and "<style" not in html, path


def test_detail_shows_evidence_and_history(
    authed: TestClient, companies: dict[str, uuid.UUID]
) -> None:
    html = authed.get(f"/companies/{companies['denov']}").text
    assert "denovsavdo.uz" in html
    assert "csv" in html
    assert "NEW → <strong>RESEARCH_PENDING</strong>" in html.replace("—", "")
    assert "agent:opportunity_scoring" in html
    assert "Lid: QUALIFIED" in html


def test_fixture_source_is_labeled(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    assert "TEST MA&#39;LUMOT" in authed.get(f"/companies/{companies['fixture']}").text
    # Also in the list, and only on the fixture company (CLAUDE.md §11).
    listing = authed.get("/companies").text
    assert listing.count("TEST MA&#39;LUMOT") == 1
    items = authed.get("/api/v1/companies").json()["items"]
    assert [i["name"] for i in items if i["is_fixture"]] == ["Fixture Firm"]


@pytest.mark.parametrize("bad", [str(uuid.uuid4()), "not-a-uuid"])
def test_detail_not_found(authed: TestClient, bad: str) -> None:
    r = authed.get(f"/companies/{bad}")
    assert r.status_code == 404 and "Topilmadi" in r.text


def test_language_switch_and_accept_language(
    authed: TestClient, companies: dict[str, uuid.UUID]
) -> None:
    r = authed.get("/lang/ru", params={"next": "/companies"})
    assert r.status_code == 303 and r.headers["location"] == "/companies"
    assert "Всего: 5" in authed.get("/companies").text
    authed.get("/lang/en", params={"next": "//evil.example"})
    assert "Total: 5" in authed.get("/companies").text
    authed.cookies.delete("smy_lang")
    page = authed.get("/login", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert page.status_code in (200, 303)


def test_login_page_language_from_header(web: TestClient) -> None:
    assert "Password" in web.get("/login", headers={"Accept-Language": "en"}).text
    assert "Пароль" in web.get("/login", headers={"Accept-Language": "ru-RU"}).text
    assert "Parol" in web.get("/login").text


def test_api_requires_auth(web: TestClient) -> None:
    r = web.get("/api/v1/companies")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_api_list_and_detail(authed: TestClient, companies: dict[str, uuid.UUID]) -> None:
    body = authed.get("/api/v1/companies", params={"country": "UZ", "per_page": 2}).json()
    assert body["meta"] == {"page": 1, "per_page": 2, "total": 4, "pages": 2}
    assert len(body["items"]) == 2
    detail = authed.get(f"/api/v1/companies/{companies['fixture']}").json()
    assert detail["sources"][0]["is_fixture"] is True
    missing = authed.get(f"/api/v1/companies/{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "http_404"


def test_pwa_manifest_and_service_worker(web: TestClient) -> None:
    manifest = web.get("/manifest.webmanifest")
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    assert manifest.json()["start_url"] == "/"
    for icon in MANIFEST["icons"]:
        assert web.get(icon["src"]).status_code == 200  # type: ignore[index]
    sw = web.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["service-worker-allowed"] == "/"
    shell = json.loads(
        re.search(r"const SHELL = (\[.*?\]);", sw.text, re.S)
        .group(1)
        .replace("'", '"')
        .replace(",\n]", "]")
    )  # type: ignore[union-attr]
    assert shell == SHELL_ASSETS
    for asset in SHELL_ASSETS:
        assert (STATIC_DIR / asset.removeprefix("/static/")).exists()


def test_all_ui_strings_translated() -> None:
    assert missing_keys() == {"uz": [], "ru": [], "en": []}


def test_htmx_vendored_file_present() -> None:
    assert (Path(STATIC_DIR) / "vendor" / "htmx-2.0.4.min.js").stat().st_size > 40_000
