"""Actors recorded on every state change: `user:<id>`, `agent:<module>`, `system:<name>`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.domain.errors import DomainError

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ActorKind(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    ident: str

    def __post_init__(self) -> None:
        if not _ID.match(self.ident):
            raise DomainError("actor id must be 1-64 chars of [A-Za-z0-9_.-]")

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.ident}"

    @classmethod
    def parse(cls, value: str) -> Actor:
        kind, sep, ident = value.partition(":")
        if not sep:
            raise DomainError(
                "actor must look like 'user:<id>', 'agent:<module>' or 'system:<name>'"
            )
        try:
            return cls(ActorKind(kind), ident)
        except ValueError as exc:
            raise DomainError(f"unknown actor kind: {kind!r}") from exc

    @classmethod
    def user(cls, user_id: str) -> Actor:
        return cls(ActorKind.USER, user_id)

    @classmethod
    def agent(cls, module: str) -> Actor:
        return cls(ActorKind.AGENT, module)

    @classmethod
    def system(cls, name: str) -> Actor:
        return cls(ActorKind.SYSTEM, name)
