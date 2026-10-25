"""OpenStreetMap business listings via the public Overpass API (free, no key).

Data © OpenStreetMap contributors, ODbL 1.0 — attribution is shown in the dashboard.
Usage policy: identify honestly (User-Agent), keep requests rare and small; the
Discovery job runs at most a few queries per cron run and caches by target interval.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.domain.discovery import OSM_FILTERS, Category, industry_from_tags
from app.infrastructure.search_providers.base import ProviderError, SearchQuery, SearchResult

logger = logging.getLogger("app.search.osm")

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "SMY-Agent/0.1 (+https://itcode.uz; business discovery for ITcoDe.Uz)"
TIMEOUT = httpx.Timeout(90.0, connect=10.0)
_SAFE_NAME = re.compile(r"^[\w .'’ʻ-]{2,64}$", re.UNICODE)  # noqa: RUF001 - Uzbek apostrophes
_COUNTRY_ISO = {"UZ": "UZ", "KZ": "KZ", "KG": "KG", "TJ": "TJ"}


def _escape(value: str) -> str:
    """Escape for an Overpass regex inside double quotes."""
    return re.sub(r'([\\".*+?^$()\[\]{}|])', r"\\\1", value)


def build_query(query: SearchQuery) -> str:
    if not query.city or not _SAFE_NAME.match(query.city):
        raise ProviderError("city is required for OpenStreetMap search", retryable=False)
    if query.country.upper() not in _COUNTRY_ISO:
        raise ProviderError("unsupported country for OpenStreetMap search", retryable=False)
    try:
        category = Category(query.category or "")
    except ValueError as exc:
        raise ProviderError("unknown category", retryable=False) from exc
    city = _escape(query.city.strip())
    country = _COUNTRY_ISO[query.country.upper()]
    selectors = []
    for key, value_re in OSM_FILTERS[category]:
        value = f'~"{value_re}"' if value_re else ""
        selectors.append(f'  nwr(area.city)["{key}"{value}]["name"];')
    # The city area must lie inside the country, and may be named in uz/en/ru.
    return (
        "[out:json][timeout:60];\n"
        f'area["ISO3166-1"="{country}"]["admin_level"="2"]->.country;\n'
        f'area(area.country)["boundary"="administrative"]'
        f'[~"^name(:(uz|en|ru))?$"~"^{city}$",i]->.city;\n'
        "(\n" + "\n".join(selectors) + "\n);\n"
        f"out center tags {max(1, min(query.limit, 200))};\n"
    )


def _values(tags: dict[str, str], *keys: str) -> tuple[str, ...]:
    out: list[str] = []
    for key in keys:
        for part in re.split(r"[;,]", tags.get(key, "")):
            if part.strip():
                out.append(part.strip())
    return tuple(dict.fromkeys(out))


def parse_elements(payload: dict[str, Any], query: SearchQuery) -> list[SearchResult]:
    results = []
    for element in payload.get("elements", []):
        tags: dict[str, str] = element.get("tags") or {}
        name = (tags.get("name:uz") or tags.get("name") or "").strip()
        if not name:
            continue
        kind, osm_id = element.get("type"), element.get("id")
        websites = _values(tags, "website", "contact:website", "url")
        results.append(
            SearchResult(
                name=name[:255],
                country=query.country.upper(),
                city=(tags.get("addr:city") or query.city or "").strip() or None,
                industry=industry_from_tags(tags),
                domain=websites[0] if websites else None,
                phones=_values(tags, "phone", "contact:phone", "contact:mobile"),
                emails=_values(tags, "email", "contact:email"),
                telegrams=_values(tags, "contact:telegram", "telegram"),
                source_url=f"https://www.openstreetmap.org/{kind}/{osm_id}",
                external_id=f"osm:{kind}/{osm_id}",
            )
        )
    return results


class OverpassSearchProvider:
    name = "osm"
    is_fixture = False

    def __init__(
        self, *, endpoint: str = DEFAULT_ENDPOINT, http: httpx.Client | None = None
    ) -> None:
        self.endpoint = endpoint
        self._http = http or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})

    def search(self, query: SearchQuery) -> list[SearchResult]:
        body = build_query(query)
        try:
            response = self._http.post(self.endpoint, data={"data": body})
        except httpx.TimeoutException:
            raise ProviderError("OpenStreetMap: timeout", retryable=True) from None
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"OpenStreetMap: network error ({type(exc).__name__})", retryable=True
            ) from None
        if response.status_code in (429, 502, 503, 504):
            raise ProviderError(f"OpenStreetMap: HTTP {response.status_code}", retryable=True)
        if response.status_code != 200:
            raise ProviderError(f"OpenStreetMap: HTTP {response.status_code}", retryable=False)
        try:
            payload = response.json()
        except ValueError:
            raise ProviderError("OpenStreetMap: invalid JSON", retryable=True) from None
        results = parse_elements(payload, query)
        logger.info(
            "osm.search",
            extra={"city": query.city, "category": query.category, "results": len(results)},
        )
        return results
