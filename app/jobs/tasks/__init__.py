"""Task handlers, keyed by job type."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.jobs.context import TaskContext
from app.jobs.tasks.conversation import SEND_JOB, run_send_reply
from app.jobs.tasks.discovery import DISCOVERY_SEARCH, run_discovery_search
from app.jobs.tasks.proposals import (
    GATE_REVIEW,
    PROPOSAL_DRAFT,
    run_proposal_draft,
    run_quality_gate,
)
from app.jobs.tasks.research import RESEARCH_AUDIT, run_research_audit
from app.jobs.tasks.scoring import SCORING_EVALUATE, run_scoring

Handler = Callable[[TaskContext, dict[str, Any]], str]

HANDLERS: dict[str, Handler] = {
    DISCOVERY_SEARCH: run_discovery_search,
    RESEARCH_AUDIT: run_research_audit,
    SCORING_EVALUATE: run_scoring,
    PROPOSAL_DRAFT: run_proposal_draft,
    GATE_REVIEW: run_quality_gate,
    SEND_JOB: run_send_reply,
}
