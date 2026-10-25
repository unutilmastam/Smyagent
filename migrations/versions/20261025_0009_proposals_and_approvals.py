"""proposals and approvals

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-25 10:00:42.050271+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                "CANCELLED",
                name="approvalstatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(length=80), nullable=False),
        sa.Column("decided_by", sa.String(length=80), nullable=True),
        sa.Column("decided_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_requests")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_approval_requests_entity",
        "approval_requests",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_status", "approval_requests", ["status", "created_at"], unique=False
    )
    op.create_table(
        "proposals",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("lead_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "NEEDS_EDIT",
                "AWAITING_APPROVAL",
                "APPROVED",
                "REJECTED",
                name="proposalstatus",
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.Enum("uz", "uz_cyrl", "ru", "en", name="language", native_enum=False, length=8),
            nullable=False,
        ),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_proposals_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_proposals_lead_id_leads"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposals")),
        sa.UniqueConstraint("lead_id", name=op.f("uq_proposals_lead_id")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_proposals_status_updated", "proposals", ["status", "updated_at"], unique=False
    )
    op.create_table(
        "proposal_versions",
        sa.Column("proposal_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("services", sa.JSON(), nullable=False),
        sa.Column("finding_ids", sa.JSON(), nullable=False),
        sa.Column("observation_keys", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("open_questions", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column(
            "gate_verdict",
            sa.Enum(
                "approved", "needs_review", "rejected", name="verdict", native_enum=False, length=16
            ),
            nullable=True,
        ),
        sa.Column("gate_issues", sa.JSON(), nullable=False),
        sa.Column(
            "gate_checked_at", app.infrastructure.database.types.UTCDateTime(), nullable=True
        ),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            name=op.f("fk_proposal_versions_proposal_id_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposal_versions")),
        sa.UniqueConstraint(
            "proposal_id", "number", name=op.f("uq_proposal_versions_proposal_id_number")
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    op.drop_table("proposal_versions")
    op.drop_table("proposals")
    op.drop_table("approval_requests")
