"""Domain-level exceptions."""

from __future__ import annotations


class DomainError(ValueError):
    """A business rule was violated."""


class InvalidTransitionError(DomainError):
    def __init__(self, entity: str, from_state: str, to_state: str) -> None:
        super().__init__(f"{entity}: transition {from_state} -> {to_state} is not allowed")
        self.entity = entity
        self.from_state = from_state
        self.to_state = to_state
