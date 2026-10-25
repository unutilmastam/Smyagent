"""Provider-neutral search contract. Business code never imports a concrete provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SearchQuery:
    country: str
    query: str
    city: str | None = None
    limit: int = 20


@dataclass(frozen=True)
class SearchResult:
    name: str
    country: str
    city: str | None = None
    industry: str | None = None
    domain: str | None = None
    phones: tuple[str, ...] = field(default_factory=tuple)
    source_url: str | None = None
    external_id: str | None = None


class SearchProvider(Protocol):
    name: str
    # True for providers that return invented data (tests/demos): results are
    # always stored with is_fixture=True and can never look like real discoveries.
    is_fixture: bool

    def search(self, query: SearchQuery) -> list[SearchResult]: ...
