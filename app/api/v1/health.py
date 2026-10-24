"""Liveness and readiness endpoints. They expose no infrastructure details."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

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
def ready(settings: Settings = Depends(get_settings)) -> ReadinessResponse:  # noqa: B008
    # Database check is added in M2 when the DB layer exists.
    checks: dict[str, Literal["ok", "fail", "skipped"]] = {
        "config": "ok",
        "database": "skipped",
    }
    status: Literal["ready", "not_ready"] = (
        "ready" if all(v != "fail" for v in checks.values()) else "not_ready"
    )
    return ReadinessResponse(status=status, checks=checks)
