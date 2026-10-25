"""discovery targets

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25 09:06:51.698936+00:00
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

import app.infrastructure.database.types

# Owner's region first (Surxondaryo), then the largest UZ cities. Editable in /discovery.
DEFAULT_CITIES = ("Denov", "Termiz", "Toshkent", "Samarqand", "Buxoro", "Qarshi")
DEFAULT_CATEGORIES = [
    "retail",
    "food",
    "hospitality",
    "health",
    "education",
    "services",
    "auto",
    "beauty",
    "craft",
]

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discovery_targets",
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("last_run_at", app.infrastructure.database.types.UTCDateTime(), nullable=True),
        sa.Column("id", app.infrastructure.database.types.GUID(length=36), nullable=False),
        sa.Column("created_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.infrastructure.database.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discovery_targets")),
        sa.UniqueConstraint("country", "city", name=op.f("uq_discovery_targets_country_city")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )

    targets = sa.table(
        "discovery_targets",
        sa.column("id", app.infrastructure.database.types.GUID()),
        sa.column("country", sa.String),
        sa.column("city", sa.String),
        sa.column("categories", sa.JSON),
        sa.column("enabled", sa.Boolean),
        sa.column("interval_days", sa.Integer),
        sa.column("created_at", app.infrastructure.database.types.UTCDateTime()),
        sa.column("updated_at", app.infrastructure.database.types.UTCDateTime()),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        targets,
        [
            {
                "id": uuid.uuid4(),
                "country": "UZ",
                "city": city,
                "categories": DEFAULT_CATEGORIES,
                "enabled": True,
                "interval_days": 7,
                "created_at": now,
                "updated_at": now,
            }
            for city in DEFAULT_CITIES
        ],
    )


def downgrade() -> None:
    op.drop_table("discovery_targets")
