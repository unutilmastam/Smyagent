"""Column helpers shared by models."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import Enum


def enum_column(enum_cls: type[PyEnum], length: int = 32) -> Enum:
    """Enum stored as VARCHAR of its values (portable; no native ENUM types)."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=False,
        length=length,
        values_callable=_values,
        validate_strings=True,
    )


def _values(enum_cls: Any) -> list[str]:
    return [member.value for member in enum_cls]
