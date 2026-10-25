"""ORM models. Import this package so every table is registered on `Base.metadata`."""

from app.infrastructure.database.models.audit import AuditLog, WorkflowEvent
from app.infrastructure.database.models.audits import ResearchFinding, WebsiteAudit
from app.infrastructure.database.models.auth import LoginAttempt, User, UserSession
from app.infrastructure.database.models.companies import Company, CompanyDomain, CompanySource
from app.infrastructure.database.models.contacts import Contact
from app.infrastructure.database.models.controls import AgentControl
from app.infrastructure.database.models.inbound import InboundEvent
from app.infrastructure.database.models.jobs import Job, JobLock
from app.infrastructure.database.models.leads import Lead
from app.infrastructure.database.models.research import ResearchRun
from app.infrastructure.database.models.runs import AgentRun, AgentRunStatus
from app.infrastructure.database.models.scoring import (
    LeadScore,
    Opportunity,
    ScoreComponent,
    ScoringSettings,
)
from app.infrastructure.database.models.targets import DiscoveryTarget

__all__ = [
    "AgentControl",
    "AgentRun",
    "AgentRunStatus",
    "AuditLog",
    "Company",
    "CompanyDomain",
    "CompanySource",
    "Contact",
    "DiscoveryTarget",
    "InboundEvent",
    "Job",
    "JobLock",
    "Lead",
    "LeadScore",
    "LoginAttempt",
    "Opportunity",
    "ResearchFinding",
    "ResearchRun",
    "ScoreComponent",
    "ScoringSettings",
    "User",
    "UserSession",
    "WebsiteAudit",
    "WorkflowEvent",
]
