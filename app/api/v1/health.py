"""Liveness and readiness endpoints. They expose no infrastructure details."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.api.deps import get_database
from app.core.config import Settings, get_settings
from app.infrastructure.database import Database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "fail", "skipped"]]


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:  # noqa: B008
    return HealthResponse(status="ok", service=settings.app_name)


@router.get("/ready", response_model=ReadinessResponse)
def ready(
    response: Response,
    database: Database = Depends(get_database),  # noqa: B008
) -> ReadinessResponse:
    # Only "ok"/"fail" per check: no versions, hosts or error text (CLAUDE.md §14).
    checks: dict[str, Literal["ok", "fail", "skipped"]] = {
        "config": "ok",
        "database": "ok" if database.ping() else "fail",
    }
    status: Literal["ready", "not_ready"] = (
        "ready" if all(v != "fail" for v in checks.values()) else "not_ready"
    )
    if status == "not_ready":
        response.status_code = 503
    return ReadinessResponse(status=status, checks=checks)
