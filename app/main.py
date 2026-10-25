"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1.companies import router as companies_api_router
from app.api.v1.control import router as control_api_router
from app.api.v1.health import router as health_router
from app.api.v1.telegram import router as telegram_router
from app.application.controls import OwnerNotifier
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from app.infrastructure.database import Database
from app.infrastructure.telegram.notifier import build_owner_notifier
from app.web.agent_settings import router as agent_settings_router
from app.web.companies import router as companies_router
from app.web.control import router as control_router
from app.web.conversations import router as conversations_router
from app.web.discovery import router as discovery_router
from app.web.discovery_targets import router as discovery_targets_router
from app.web.errors import register_web_exception_handlers
from app.web.jobs import router as jobs_router
from app.web.leads import router as leads_router
from app.web.outreach import router as outreach_router
from app.web.proposals import router as proposals_router
from app.web.pwa import router as pwa_router
from app.web.routes import router as web_router
from app.web.templating import STATIC_DIR

build_notifier = build_owner_notifier


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
    notifier: OwnerNotifier | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    docs_enabled = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    # Engine creation does not connect; the first query does. ASGI lifespan is not
    # relied upon (ADR-0001), so the database is attached here.
    app.state.database = database or Database(settings.database_url.get_secret_value())
    app.state.notifier = notifier or build_notifier(settings)
    register_exception_handlers(app)
    register_web_exception_handlers(app)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(companies_api_router, prefix="/api/v1")
    app.include_router(telegram_router, prefix="/api/v1")
    app.include_router(control_api_router, prefix="/api/v1")
    app.include_router(web_router)
    # Before companies_router so /companies/new is not captured by /companies/{id}.
    app.include_router(discovery_router)
    app.include_router(discovery_targets_router)
    app.include_router(companies_router)
    app.include_router(control_router)
    app.include_router(leads_router)
    app.include_router(proposals_router)
    app.include_router(agent_settings_router)
    app.include_router(conversations_router)
    app.include_router(outreach_router)
    app.include_router(jobs_router)
    app.include_router(pwa_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app
