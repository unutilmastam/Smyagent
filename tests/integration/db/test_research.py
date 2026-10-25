"""Research & Audit agent: offline (fake fetcher), all outcomes."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.domain.companies import ResearchState
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Company,
    ResearchFinding,
    ResearchRun,
    WebsiteAudit,
)
from app.infrastructure.http_fetcher.fetcher import FetchError, FetchResult, RobotsDisallowedError
from app.infrastructure.http_fetcher.policy import BlockedURLError
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.jobs.runner import JobRunner
from app.jobs.tasks.research import enqueue_new_companies

PAGE = (
    b'<html lang="uz"><head><title>Mebel</title></head><body>'
    b"<p>Xush kelibsiz</p><p>&copy; 2019</p></body></html>"
)


class FakeFetcher:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.urls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.urls.append(url)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FetchResult(
            requested_url=url,
            final_url=url.replace("http://", "https://"),
            status_code=200,
            content_type="text/html",
            body=self.outcome,
            elapsed_ms=900,
        )

    def close(self) -> None:
        pass


def _company(db: Database, domain: str | None = "mebel.uz") -> Any:
    with db.transaction() as s:
        return (
            CompanyRepository(s)
            .add(
                NewCompany(
                    name=f"Mebel {domain}",
                    country="UZ",
                    city="Denov",
                    domains=(domain,) if domain else (),
                )
            )
            .id
        )


def _run(db: Database, settings: Settings, fetcher: FakeFetcher) -> Any:
    runner = JobRunner(
        db,
        settings,
        search_provider_factory=lambda _s: None,
        fetcher_factory=lambda: fetcher,
        worker_id="t",
    )  # type: ignore[arg-type,return-value]
    return runner.run(max_jobs=5, max_seconds=60)


def _state(db: Database, cid: Any) -> ResearchState:
    with db.transaction() as s:
        return s.get(Company, cid).research_state  # type: ignore[union-attr]


def _findings(db: Database, cid: Any) -> dict[str, ResearchFinding]:
    with db.transaction() as s:
        return {
            f.key: f
            for f in s.scalars(select(ResearchFinding).where(ResearchFinding.company_id == cid))
        }


def test_new_companies_are_queued_once(db: Database) -> None:
    _company(db)
    with db.transaction() as s:
        assert enqueue_new_companies(s) == 1
    with db.transaction() as s:
        assert enqueue_new_companies(s) == 0  # already RESEARCH_PENDING


def test_audit_saves_evidence_without_raw_html(db: Database, settings: Settings) -> None:
    cid = _company(db)
    fetcher = FakeFetcher(PAGE)
    summary = _run(db, settings, fetcher)
    assert summary.succeeded == 1 and "ball" in summary.messages[0]
    assert fetcher.urls == ["https://mebel.uz/"]
    assert _state(db, cid) is ResearchState.RESEARCHED
    with db.transaction() as s:
        audit = s.scalars(select(WebsiteAudit)).one()
        run = s.scalars(select(ResearchRun)).one()
    assert (
        audit.score is not None and audit.status_code == 200 and len(audit.content_hash or "") == 64
    )
    assert "<html" not in (audit.text_excerpt or "") and "Xush kelibsiz" in (
        audit.text_excerpt or ""
    )
    assert any(c["key"] == "mobile_viewport" and c["severity"] == "bad" for c in audit.checks)
    assert run.status.value == "SUCCEEDED"
    findings = _findings(db, cid)
    assert findings["not_mobile_friendly"].source_url == "https://mebel.uz/"
    assert findings["possibly_outdated"].kind.value == "inference"


def test_no_website_is_a_finding(db: Database, settings: Settings) -> None:
    cid = _company(db, domain=None)
    _run(db, settings, FakeFetcher(PAGE))
    assert _state(db, cid) is ResearchState.RESEARCHED
    assert "no_website" in _findings(db, cid)


@pytest.mark.parametrize("category", ["dns", "connect", "timeout"])
def test_unreachable_site_is_a_finding_not_a_crash(
    db: Database, settings: Settings, category: str
) -> None:
    cid = _company(db)
    fetcher = FakeFetcher(FetchError(category, "x"))
    _run(db, settings, fetcher)
    assert _state(db, cid) is ResearchState.RESEARCHED
    assert "website_unreachable" in _findings(db, cid)
    if category in ("connect", "timeout"):
        assert fetcher.urls == ["https://mebel.uz/", "http://mebel.uz/"]  # retried over http


def test_blocked_address_fails_research(db: Database, settings: Settings) -> None:
    cid = _company(db)
    _run(db, settings, FakeFetcher(BlockedURLError("private")))
    assert _state(db, cid) is ResearchState.RESEARCH_FAILED
    assert _findings(db, cid) == {}


def test_robots_disallow_is_respected_and_recorded(db: Database, settings: Settings) -> None:
    cid = _company(db)
    _run(db, settings, FakeFetcher(RobotsDisallowedError("https://mebel.uz/")))
    assert "audit_not_allowed" in _findings(db, cid)
    with db.transaction() as s:
        assert s.scalars(select(WebsiteAudit)).first() is None


def test_one_failing_site_does_not_stop_the_batch(db: Database, settings: Settings) -> None:
    good = _company(db, "good.uz")
    bad = _company(db, "bad.uz")

    class Mixed(FakeFetcher):
        def fetch(self, url: str) -> FetchResult:
            if "bad.uz" in url:
                raise RuntimeError("parser exploded")
            return super().fetch(url)

    summary = _run(db, settings, Mixed(PAGE))
    assert summary.succeeded == 1 and summary.failed == 1
    assert _state(db, good) is ResearchState.RESEARCHED
    assert _state(db, bad) is ResearchState.RESEARCH_PENDING  # retry possible later
