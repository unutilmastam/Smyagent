"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.infrastructure.database import Database


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database
