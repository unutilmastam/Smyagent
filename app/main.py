"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from app.infrastructure.database import Database
from app.web.errors import register_web_exception_handlers
from app.web.routes import router as web_router
from app.web.templating import STATIC_DIR


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
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
    register_exception_handlers(app)
    register_web_exception_handlers(app)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app
