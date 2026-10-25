from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.domain.discovery import (
    Category,
    TargetSpec,
    industry_from_tags,
    is_due,
    parse_categories,
)
from app.domain.errors import DomainError
from app.infrastructure.search_providers.base import ProviderError, SearchQuery
from app.infrastructure.search_providers.osm import (
    USER_AGENT,
    OverpassSearchProvider,
    build_query,
    parse_elements,
)

Q = SearchQuery(country="UZ", query="retail", city="Denov", limit=50, category="retail")

# Shape of a real Overpass `out center tags` response (values invented for the test).
PAYLOAD = {
    "elements": [
        {
            "type": "node",
            "id": 101,
            "tags": {
                "name": "Denov Mebel",
                "name:uz": "Denov Mebel",
                "shop": "furniture",
                "phone": "+998 90 111 22 33;+998 91 444 55 66",
                "website": "https://denovmebel.uz",
                "contact:telegram": "https://t.me/denov_mebel",
            },
        },
        {
            "type": "way",
            "id": 202,
            "center": {"lat": 38.2, "lon": 67.9},
            "tags": {
                "name": "Surxon Market",
                "shop": "supermarket",
                "addr:city": "Denov",
                "contact:email": "info@surxon.uz",
            },
        },
        {"type": "node", "id": 303, "tags": {"shop": "clothes"}},  # no name -> skipped
    ]
}


def test_build_query_is_scoped_and_escaped() -> None:
    q = build_query(Q)
    assert '["ISO3166-1"="UZ"]' in q
    assert '~"^Denov$",i' in q
    assert '["shop"~"^(supermarket|' in q
    assert "out center tags 50;" in q
    risky = build_query(SearchQuery(country="UZ", query="x", city="O'zbek.", category="food"))
    assert "O'zbek\\." in risky


@pytest.mark.parametrize(
    "query",
    [
        SearchQuery(country="UZ", query="x", city='Denov"];out;', category="retail"),
        SearchQuery(country="UZ", query="x", city=None, category="retail"),
        SearchQuery(country="RU", query="x", city="Moskva", category="retail"),
        SearchQuery(country="UZ", query="x", city="Denov", category="weapons"),
    ],
)
def test_build_query_rejects_bad_input(query: SearchQuery) -> None:
    with pytest.raises(ProviderError) as exc:
        build_query(query)
    assert exc.value.retryable is False


def test_parse_elements() -> None:
    results = parse_elements(PAYLOAD, Q)
    assert [r.name for r in results] == ["Denov Mebel", "Surxon Market"]
    first, second = results
    assert first.phones == ("+998 90 111 22 33", "+998 91 444 55 66")
    assert first.domain == "https://denovmebel.uz"
    assert first.telegrams == ("https://t.me/denov_mebel",)
    assert first.industry == "Retail: furniture"
    assert first.source_url == "https://www.openstreetmap.org/node/101"
    assert first.external_id == "osm:node/101"
    assert second.emails == ("info@surxon.uz",) and second.city == "Denov"


def _provider(handler: object) -> OverpassSearchProvider:
    http = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT})  # type: ignore[arg-type]
    return OverpassSearchProvider(http=http)


def test_search_posts_query_with_honest_user_agent() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers["user-agent"]
        seen["body"] = request.content.decode()
        return httpx.Response(200, json=PAYLOAD)

    assert len(_provider(handler).search(Q)) == 2
    assert "SMY-Agent" in seen["ua"] and "itcode.uz" in seen["ua"]
    assert "data=" in seen["body"]


@pytest.mark.parametrize(
    ("status", "retryable"), [(429, True), (504, True), (400, False), (403, False)]
)
def test_http_errors(status: int, retryable: bool) -> None:
    provider = _provider(lambda request: httpx.Response(status, text="error"))
    with pytest.raises(ProviderError) as exc:
        provider.search(Q)
    assert exc.value.retryable is retryable


def test_timeout_is_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError) as exc:
        _provider(handler).search(Q)
    assert exc.value.retryable is True


def test_discovery_domain_rules() -> None:
    now = datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert is_due(None, timedelta(days=7), now)
    assert not is_due(now - timedelta(days=6), timedelta(days=7), now)
    assert is_due(now - timedelta(days=7), timedelta(days=7), now)
    assert parse_categories(["food", "food", "retail"]) == (Category.FOOD, Category.RETAIL)
    with pytest.raises(DomainError):
        parse_categories(["nope"])
    with pytest.raises(DomainError):
        TargetSpec(country="UZ", city="Denov", categories=())
    with pytest.raises(DomainError):
        TargetSpec(country="UZ", city="<script>", categories=(Category.FOOD,))
    assert industry_from_tags({"amenity": "car_wash"}) == "Services: car wash"
    assert industry_from_tags({"name": "x"}) is None
