"""Task handlers, keyed by job type."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.jobs.context import TaskContext
from app.jobs.tasks.discovery import DISCOVERY_SEARCH, run_discovery_search
from app.jobs.tasks.research import RESEARCH_AUDIT, run_research_audit

Handler = Callable[[TaskContext, dict[str, Any]], str]

HANDLERS: dict[str, Handler] = {
    DISCOVERY_SEARCH: run_discovery_search,
    RESEARCH_AUDIT: run_research_audit,
}
