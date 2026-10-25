"""Discovery agent task: search one city + category and ingest the results."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.budget import BudgetService, UsageRecord
from app.application.discovery import DiscoveryService, IntakeStatus
from app.domain.actors import Actor
from app.domain.agents import AgentModule
from app.domain.budget import BudgetWindow, UsageKind, next_window
from app.domain.discovery import Category, is_due
from app.infrastructure.database.models import DiscoveryTarget
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from app.infrastructure.repositories.companies import NewCompany
from app.infrastructure.repositories.jobs import JobRepository
from app.infrastructure.search_providers.base import ProviderError, SearchQuery
from app.jobs.context import DeferTaskError, RetryableTaskError, TaskContext

DISCOVERY_SEARCH = "discovery.search"
ACTOR = Actor.agent(AgentModule.DISCOVERY.value)


def enqueue_due_targets(
    session: Session, *, now: datetime | None = None, force_target: uuid.UUID | None = None
) -> int:
    """Create one job per (target, category) for targets that are due. Idempotent per day.

    `force_target` ("run now" from the dashboard) ignores the interval.
    """
    now = now or utcnow()
    jobs = JobRepository(session)
    created = 0
    stmt = select(DiscoveryTarget).where(DiscoveryTarget.enabled.is_(True))
    if force_target is not None:
        stmt = select(DiscoveryTarget).where(DiscoveryTarget.id == force_target)
    for target in session.scalars(stmt):
        due = is_due(target.last_run_at, timedelta(days=max(1, target.interval_days)), now)
        if force_target is None and not due:
            continue
        stamp = now.strftime("%Y%m%d%H%M") if force_target else now.strftime("%Y%m%d")
        for category in target.categories:
            _, new = jobs.enqueue(
                job_type=DISCOVERY_SEARCH,
                agent_module=AgentModule.DISCOVERY.value,
                payload={"target_id": str(target.id), "category": category},
                idempotency_key=f"discovery:{target.id}:{category}:{stamp}",
                max_attempts=3,
            )
            created += int(new)
        target.last_run_at = now
    return created


def run_discovery_search(ctx: TaskContext, payload: dict[str, Any]) -> str:
    target_id = uuid.UUID(str(payload["target_id"]))
    category = Category(str(payload["category"]))
    with ctx.database.transaction() as session:
        target = session.get(DiscoveryTarget, target_id)
        if target is None:
            return "target deleted"
        country, city = target.country, target.city
        limit = AgentSettingsRepository(session).get(AgentModule.DISCOVERY).results_per_search

    provider = ctx.search_provider_factory(ctx.settings)
    if provider is None:
        return "automatic discovery is off (SEARCH_PROVIDER is empty)"
    if getattr(provider, "paid", False):
        # Paid providers stay inside DAILY_SEARCH_LIMIT (e.g. Google Places free quota).
        with ctx.database.transaction() as session:
            used = BudgetService(session, ctx.settings).searches_today(provider.name)
        if used >= ctx.settings.daily_search_limit:
            tomorrow = next_window(BudgetWindow.DAY, utcnow(), ctx.settings.default_timezone)
            raise DeferTaskError(f"daily search limit {ctx.settings.daily_search_limit}", tomorrow)
    ctx.progress(f"{city}: {category.value} qidirilmoqda", 5)
    try:
        results = provider.search(
            SearchQuery(
                country=country,
                query=category.value,
                city=city,
                limit=limit,
                category=category.value,
            )
        )
    except ProviderError as exc:
        if exc.retryable:
            raise RetryableTaskError(str(exc)) from None
        raise
    ctx.record_usage(UsageRecord(provider=provider.name, module="", kind=UsageKind.SEARCH))

    created = duplicates = invalid = 0
    for index, item in enumerate(results, start=1):
        ctx.checkpoint()  # stop/pause takes effect between companies
        data = NewCompany(
            name=item.name,
            country=item.country,
            city=item.city,
            industry=item.industry,
            domains=(item.domain,) if item.domain else (),
            phones=item.phones,
            emails=item.emails,
            telegrams=item.telegrams,
            source_type=provider.name,
            source_url=item.source_url,
            external_id=item.external_id,
            is_fixture=provider.is_fixture,
        )
        with ctx.database.transaction() as session:
            result = DiscoveryService(session).ingest(data, ACTOR)
        if result.status is IntakeStatus.CREATED:
            created += 1
        elif result.status is IntakeStatus.DUPLICATE:
            duplicates += 1
        else:
            invalid += 1
        if index % 5 == 0 or index == len(results):
            ctx.progress(
                f"{city}: {category.value} — {index}/{len(results)} ({created} yangi)",
                5 + int(95 * index / max(1, len(results))),
            )
    summary = f"{city}/{category.value}: {created} yangi, {duplicates} dublikat, {invalid} xato"
    ctx.progress(summary, 100)
    return summary
