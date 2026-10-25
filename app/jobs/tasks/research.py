"""Research & Audit agent task: audit a company's website and record findings."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.workflow import WorkflowService
from app.domain.actors import Actor
from app.domain.agents import AgentModule
from app.domain.audit import (
    NO_WEBSITE_FINDING,
    AuditInput,
    Finding,
    Kind,
    audit,
    unreachable_finding,
)
from app.domain.companies import ResearchState
from app.infrastructure.database.models import (
    Company,
    CompanyDomain,
    ResearchFinding,
    ResearchRun,
    WebsiteAudit,
)
from app.infrastructure.database.models.research import ResearchRunStatus
from app.infrastructure.database.types import utcnow
from app.infrastructure.http_fetcher.fetcher import FetchError, FetchResult, RobotsDisallowedError
from app.infrastructure.http_fetcher.policy import BlockedURLError
from app.infrastructure.repositories.jobs import JobRepository
from app.jobs.context import TaskContext

RESEARCH_AUDIT = "research.audit"
ACTOR = Actor.agent(AgentModule.RESEARCH_AUDIT.value)
SCHEDULER = Actor.system("cron")
# Network-level failures worth a second try over plain http.
_RETRY_OVER_HTTP = frozenset({"connect", "tls", "timeout"})


def enqueue_new_companies(session: Session, *, limit: int = 20) -> int:
    """Queue research for NEW companies (oldest first) and mark them RESEARCH_PENDING."""
    jobs = JobRepository(session)
    workflow = WorkflowService(session)
    queued = 0
    companies = session.scalars(
        select(Company)
        .where(Company.research_state == ResearchState.NEW)
        .order_by(Company.created_at, Company.id)
        .limit(limit)
    ).all()
    for company in companies:
        _, created = jobs.enqueue(
            job_type=RESEARCH_AUDIT,
            agent_module=AgentModule.RESEARCH_AUDIT.value,
            payload={"company_id": str(company.id)},
            idempotency_key=f"research:{company.id}:{company.updated_at:%Y%m%d%H%M%S}",
        )
        workflow.transition_company(
            company.id, ResearchState.RESEARCH_PENDING, SCHEDULER, "new company"
        )
        queued += int(created)
    return queued


def _save_findings(
    session: Session,
    company_id: uuid.UUID,
    run_id: uuid.UUID,
    findings: list[Finding],
    source_url: str | None,
) -> None:
    now = utcnow()
    for f in findings:
        session.add(
            ResearchFinding(
                company_id=company_id,
                research_run_id=run_id,
                key=f.key,
                kind=f.kind,
                statement=f.statement[:500],
                confidence=f.confidence,
                source_url=source_url,
                retrieved_at=now,
            )
        )


def _finish(
    ctx: TaskContext,
    company_id: uuid.UUID,
    run_id: uuid.UUID,
    state: ResearchState,
    findings: list[Finding],
    source_url: str | None,
    *,
    audit_row: WebsiteAudit | None = None,
    error: str | None = None,
) -> None:
    with ctx.database.transaction() as session:
        if audit_row is not None:
            audit_row.research_run_id = run_id
            session.add(audit_row)
        _save_findings(session, company_id, run_id, findings, source_url)
        run = session.get(ResearchRun, run_id)
        if run is not None:
            run.status = (
                ResearchRunStatus.FAILED
                if state is ResearchState.RESEARCH_FAILED
                else ResearchRunStatus.SUCCEEDED
            )
            run.finished_at = utcnow()
            run.error_message = error
        company = session.get(Company, company_id)
        if company is not None and company.research_state is ResearchState.RESEARCH_PENDING:
            WorkflowService(session).transition_company(
                company_id, state, ACTOR, error or "audited"
            )


def _fetch_homepage(ctx: TaskContext, domain: str) -> FetchResult:
    fetcher = ctx.fetcher_factory()
    try:
        try:
            return fetcher.fetch(f"https://{domain}/")
        except FetchError as exc:
            if exc.category not in _RETRY_OVER_HTTP:
                raise
            return fetcher.fetch(f"http://{domain}/")
    finally:
        fetcher.close()


def run_research_audit(ctx: TaskContext, payload: dict[str, Any]) -> str:
    company_id = uuid.UUID(str(payload["company_id"]))
    with ctx.database.transaction() as session:
        company = session.get(Company, company_id)
        if company is None:
            return "company deleted"
        if company.research_state is ResearchState.NEW:  # queued by hand / old job
            WorkflowService(session).transition_company(
                company_id, ResearchState.RESEARCH_PENDING, ACTOR, "audit started"
            )
        domains = session.scalars(
            select(CompanyDomain.domain)
            .where(CompanyDomain.company_id == company_id)
            .order_by(CompanyDomain.is_primary.desc())
        ).all()
        name = company.name
        run = ResearchRun(
            company_id=company_id, status=ResearchRunStatus.RUNNING, started_at=utcnow()
        )
        session.add(run)
        session.flush()
        run_id = run.id

    if not domains:
        _finish(ctx, company_id, run_id, ResearchState.RESEARCHED, [NO_WEBSITE_FINDING], None)
        return f"{name}: sayt yo'q"

    domain = domains[0]
    ctx.progress(f"{domain} tekshirilmoqda (1/3)", 10)
    now = utcnow()
    try:
        result = _fetch_homepage(ctx, domain)
    except BlockedURLError:
        _finish(
            ctx,
            company_id,
            run_id,
            ResearchState.RESEARCH_FAILED,
            [],
            None,
            error="blocked_address",
        )
        return f"{domain}: manzil bloklandi (xavfsizlik)"
    except RobotsDisallowedError:
        finding = Finding(
            "audit_not_allowed",
            Kind.FACT,
            "The site's robots.txt asks automated tools not to read it; not audited.",
            1.0,
        )
        _finish(ctx, company_id, run_id, ResearchState.RESEARCHED, [finding], f"https://{domain}/")
        return f"{domain}: robots.txt ruxsat bermadi"
    except FetchError as exc:
        row = WebsiteAudit(
            company_id=company_id,
            url=f"https://{domain}/",
            error_category=exc.category,
            fetched_at=now,
        )
        _finish(
            ctx,
            company_id,
            run_id,
            ResearchState.RESEARCHED,
            [unreachable_finding(exc.category)],
            f"https://{domain}/",
            audit_row=row,
        )
        return f"{domain}: ochilmadi ({exc.category})"

    ctx.checkpoint()
    ctx.progress(f"{domain} tahlil qilinmoqda (2/3)", 60)
    report = audit(
        AuditInput(
            requested_url=result.requested_url,
            final_url=result.final_url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
            size_bytes=len(result.body),
            html=result.text,
            redirects=tuple(result.redirects),
            current_year=now.year,
        )
    )
    row = WebsiteAudit(
        company_id=company_id,
        url=result.requested_url,
        final_url=result.final_url[:2048],
        status_code=result.status_code,
        response_ms=result.elapsed_ms,
        size_bytes=len(result.body),
        title=report.title[:300] or None,
        score=report.score,
        checks=[
            {"key": c.key, "severity": c.severity.value, "evidence": c.evidence[:300]}
            for c in report.checks
        ],
        content_hash=hashlib.sha256(report.facts.text.encode()).hexdigest(),
        text_excerpt=report.text_excerpt,
        fetched_at=now,
    )
    ctx.progress(f"{domain} saqlanmoqda (3/3)", 90)
    _finish(
        ctx,
        company_id,
        run_id,
        ResearchState.RESEARCHED,
        report.findings,
        result.final_url,
        audit_row=row,
    )
    return f"{domain}: ball {report.score}/100, {len(report.findings)} ta topilma"
