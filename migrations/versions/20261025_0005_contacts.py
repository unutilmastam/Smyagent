"""contacts

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25 00:13:15.190454+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("company_id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("phone", "email", "telegram", name="contactkind", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("value", sa.String(length=191), nullable=False),
        sa.Column("is_role_address", sa.Boolean(), nullable=False),
        sa.Column("source_id", app.infrastructure.database.types.GUID(length=36), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_contacts_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["company_sources.id"],
            name=op.f("fk_contacts_source_id_company_sources"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint(
            "company_id", "kind", "value", name=op.f("uq_contacts_company_id_kind_value")
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index("ix_contacts_kind_value", "contacts", ["kind", "value"], unique=False)


def downgrade() -> None:
    op.drop_table("contacts")
