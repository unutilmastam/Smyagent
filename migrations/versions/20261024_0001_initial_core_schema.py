"""initial core schema

Revision ID: 0001
Revises:
Create Date: 2026-10-24 23:20:16.858730+00:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

# Explicit on every table: shared hosts may default to latin1 / MyISAM (ADR-0002).
MYSQL_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}
CONTROL_KEYS = (
    "global",
    "orchestrator",
    "discovery",
    "research_audit",
    "opportunity_scoring",
    "proposal_requirements",
    "conversation",
    "quality_gate",
)

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_controls",
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "ACTIVE", "PAUSED", "STOPPED", name="controlstate", native_enum=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("changed_by", sa.String(length=80), nullable=False),
        sa.Column("changed_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("module", name=op.f("pk_agent_controls")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_table(
        "audit_logs",
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"], unique=False
    )
    op.create_table(
        "companies",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=191), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("city", sa.String(length=191), nullable=True),
        sa.Column("normalized_city", sa.String(length=191), nullable=True),
        sa.Column("industry", sa.String(length=191), nullable=True),
        sa.Column(
            "research_state",
            sa.Enum(
                "NEW",
                "RESEARCH_PENDING",
                "RESEARCHED",
                "ANALYZED",
                "RESEARCH_FAILED",
                "ARCHIVED",
                name="researchstate",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index(
        "ix_companies_country_state", "companies", ["country", "research_state"], unique=False
    )
    op.create_index(
        "ix_companies_name_city", "companies", ["normalized_name", "normalized_city"], unique=False
    )
    op.create_table(
        "job_locks",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("holder", sa.String(length=64), nullable=False),
        sa.Column("acquired_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_job_locks")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_table(
        "jobs",
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("agent_module", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                "BUDGET_DEFERRED",
                name="jobstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=191), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("claimed_by", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("heartbeat_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("finished_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_jobs_idempotency_key")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index("ix_jobs_module_status", "jobs", ["agent_module", "status"], unique=False)
    op.create_index("ix_jobs_status_run_after", "jobs", ["status", "run_after"], unique=False)
    op.create_table(
        "workflow_events",
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_events")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index("ix_workflow_events_created", "workflow_events", ["created_at"], unique=False)
    op.create_index(
        "ix_workflow_events_entity",
        "workflow_events",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "company_domains",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("domain", sa.String(length=191), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_domains_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_domains")),
        sa.UniqueConstraint("domain", name=op.f("uq_company_domains_domain")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index(
        op.f("ix_company_domains_company_id"), "company_domains", ["company_id"], unique=False
    )
    op.create_table(
        "company_sources",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("external_id", sa.String(length=191), nullable=True),
        sa.Column("retrieved_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("is_fixture", sa.Boolean(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_sources_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_sources")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index(
        op.f("ix_company_sources_company_id"), "company_sources", ["company_id"], unique=False
    )
    op.create_index(
        "ix_company_sources_type_external",
        "company_sources",
        ["source_type", "external_id"],
        unique=False,
    )
    op.create_table(
        "leads",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column(
            "stage",
            sa.Enum(
                "CANDIDATE",
                "QUALIFIED",
                "PROPOSAL_DRAFTED",
                "AWAITING_APPROVAL",
                "APPROVED",
                "CONTACTED",
                "RESPONDED",
                "MEETING",
                "WON",
                "CLOSED",
                "LOST",
                "DISQUALIFIED",
                "DO_NOT_CONTACT",
                "PAUSED",
                "ERROR",
                name="leadstage",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "resume_stage",
            sa.Enum(
                "CANDIDATE",
                "QUALIFIED",
                "PROPOSAL_DRAFTED",
                "AWAITING_APPROVAL",
                "APPROVED",
                "CONTACTED",
                "RESPONDED",
                "MEETING",
                "WON",
                "CLOSED",
                "LOST",
                "DISQUALIFIED",
                "DO_NOT_CONTACT",
                "PAUSED",
                "ERROR",
                name="leadstage",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column(
            "stage_changed_at", app.infrastructure.database.types.UTCDateTime(), nullable=False
        ),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_leads_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
        sa.UniqueConstraint("company_id", name=op.f("uq_leads_company_id")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index("ix_leads_stage_changed", "leads", ["stage", "stage_changed_at"], unique=False)
    op.create_table(
        "research_runs",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                name="researchrunstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("started_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("finished_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_research_runs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_runs")),
        **MYSQL_TABLE_OPTIONS,
    )
    op.create_index(
        "ix_research_runs_company_created",
        "research_runs",
        ["company_id", "created_at"],
        unique=False,
    )

    controls = sa.table(
        "agent_controls",
        sa.column("module", sa.String),
        sa.column("state", sa.String),
        sa.column("changed_by", sa.String),
        sa.column("changed_at", app.infrastructure.database.types.UTCDateTime()),
        sa.column("reason", sa.String),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        controls,
        [
            {
                "module": key,
                "state": "ACTIVE",
                "changed_by": "system:migration",
                "changed_at": now,
                "reason": "initial",
            }
            for key in CONTROL_KEYS
        ],
    )


def downgrade() -> None:
    # Dropping a table drops its indexes; dropping FK-backing indexes first fails on MySQL.
    op.drop_table("research_runs")
    op.drop_table("leads")
    op.drop_table("company_sources")
    op.drop_table("company_domains")
    op.drop_table("workflow_events")
    op.drop_table("jobs")
    op.drop_table("job_locks")
    op.drop_table("companies")
    op.drop_table("audit_logs")
    op.drop_table("agent_controls")
