"""opportunities and scores

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-25 09:37:12.982612+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scoring_settings",
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("qualify_threshold", sa.Integer(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("updated_by", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_scoring_settings")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "opportunities",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("finding_ids", sa.JSON(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_opportunities_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opportunities")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index("ix_opportunities_company", "opportunities", ["company_id"], unique=False)
    op.create_table(
        "lead_scores",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("lead_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("missing", sa.JSON(), nullable=False),
        sa.Column("computed_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_lead_scores_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_scores_lead_id_leads"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_scores")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_lead_scores_company_computed",
        "lead_scores",
        ["company_id", "computed_at"],
        unique=False,
    )
    op.create_index("ix_lead_scores_total", "lead_scores", ["total"], unique=False)
    op.create_table(
        "score_components",
        sa.Column("score_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("component", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("explanation", sa.String(length=300), nullable=False),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["score_id"],
            ["lead_scores.id"],
            name=op.f("fk_score_components_score_id_lead_scores"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_components")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        op.f("ix_score_components_score_id"), "score_components", ["score_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("score_components")
    op.drop_table("lead_scores")
    op.drop_table("opportunities")
    op.drop_table("scoring_settings")
