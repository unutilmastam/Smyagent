"""Deterministic fake provider for development and tests. Its data is fictional."""

from __future__ import annotations

from app.infrastructure.search_providers.base import SearchQuery, SearchResult

_SAMPLES = [
    ("Namuna Savdo", "Retail", "namuna-savdo.example"),
    ("Namuna Mebel", "Furniture", "namuna-mebel.example"),
    ("Namuna Logistika", "Logistics", None),
]


class FixtureSearchProvider:
    name = "fixture"
    is_fixture = True

    def search(self, query: SearchQuery) -> list[SearchResult]:
        city = query.city or "Toshkent"
        return [
            SearchResult(
                name=f"{name} ({city})",
                country=query.country,
                city=city,
                industry=industry,
                domain=domain,
                source_url=None,
                external_id=f"fixture-{i}-{city.lower()}",
            )
            for i, (name, industry, domain) in enumerate(_SAMPLES[: query.limit])
        ]
