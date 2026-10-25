"""Public business contacts of a company (phones, emails, Telegram)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.contacts import ContactKind
from app.infrastructure.database.base import Base, Timestamps, UUIDPrimaryKey
from app.infrastructure.database.models._columns import enum_column
from app.infrastructure.database.types import GUID


class Contact(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "contacts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE")
    )
    kind: Mapped[ContactKind] = mapped_column(enum_column(ContactKind, length=16))
    # Normalized value (E.164 phone, lowercase email, @telegram).
    value: Mapped[str] = mapped_column(String(191))
    # Role address (info@, sales@ ...) vs. an address that might name a person.
    is_role_address: Mapped[bool] = mapped_column(Boolean, default=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("company_sources.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("company_id", "kind", "value"),
        # Duplicate detection across companies (same phone => probably same company).
        Index("ix_contacts_kind_value", "kind", "value"),
    )
