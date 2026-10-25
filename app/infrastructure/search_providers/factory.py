"""Build the configured search provider (SEARCH_PROVIDER)."""

from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.search_providers.base import SearchProvider
from app.infrastructure.search_providers.fixture import FixtureSearchProvider
from app.infrastructure.search_providers.osm import OverpassSearchProvider

# Providers that need no API key.
KEYLESS_PROVIDERS = frozenset({"osm", "fixture"})


def build_search_provider(settings: Settings) -> SearchProvider | None:
    name = settings.search_provider.strip().lower()
    if name == "osm":
        return OverpassSearchProvider()
    if name == "fixture":
        return FixtureSearchProvider()
    return None  # "" = automatic discovery off; other providers arrive with credentials
