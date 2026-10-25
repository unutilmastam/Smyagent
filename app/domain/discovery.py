"""What the Discovery agent looks for (CLAUDE.md §8.1, §8.2).

Categories are business types that commonly need software services. Each maps to
OpenStreetMap tags (public business listings, ODbL) and is configurable per target.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from app.domain.errors import DomainError


class Category(str, Enum):
    RETAIL = "retail"
    FOOD = "food"
    HOSPITALITY = "hospitality"
    HEALTH = "health"
    EDUCATION = "education"
    SERVICES = "services"
    AUTO = "auto"
    BEAUTY = "beauty"
    CRAFT = "craft"


# OSM key -> value regex ("" = any value). Only named features are queried.
OSM_FILTERS: dict[Category, tuple[tuple[str, str], ...]] = {
    Category.RETAIL: (
        (
            "shop",
            "^(supermarket|clothes|electronics|furniture|hardware|mobile_phone|cosmetics|"
            "shoes|jewelry|gift|bakery|butcher|convenience|department_store|doityourself|"
            "houseware|books|toys|sports|optician)$",
        ),
    ),
    Category.FOOD: (("amenity", "^(restaurant|cafe|fast_food)$"),),
    Category.HOSPITALITY: (("tourism", "^(hotel|guest_house|hostel|motel)$"),),
    Category.HEALTH: (("amenity", "^(clinic|dentist|pharmacy|doctors)$"), ("healthcare", "")),
    Category.EDUCATION: (
        ("amenity", "^(language_school|driving_school|training|music_school|prep_school)$"),
    ),
    Category.SERVICES: (
        (
            "office",
            "^(company|it|lawyer|accountant|estate_agent|insurance|travel_agent|"
            "advertising_agency|logistics|consulting)$",
        ),
    ),
    Category.AUTO: (("shop", "^(car|car_repair|car_parts|tyres)$"), ("amenity", "^car_wash$")),
    Category.BEAUTY: (("shop", "^(beauty|hairdresser|massage)$"),),
    Category.CRAFT: (("craft", ""),),
}

INDUSTRY_LABELS: dict[str, str] = {
    "shop": "Retail",
    "amenity": "Services",
    "tourism": "Hospitality",
    "healthcare": "Healthcare",
    "office": "Office",
    "craft": "Craft",
}

DEFAULT_INTERVAL = timedelta(days=7)
MAX_CITY_LENGTH = 64
_CITY = re.compile(r"^[\w .'’ʻ-]{2,64}$", re.UNICODE)  # noqa: RUF001 - Uzbek apostrophes


@dataclass(frozen=True)
class TargetSpec:
    country: str
    city: str
    categories: tuple[Category, ...]

    def __post_init__(self) -> None:
        if not _CITY.match(self.city):
            raise DomainError("city name has invalid characters")
        if not self.categories:
            raise DomainError("choose at least one category")


def parse_categories(values: list[str] | tuple[str, ...]) -> tuple[Category, ...]:
    result = []
    for value in values:
        try:
            result.append(Category(value))
        except ValueError as exc:
            raise DomainError(f"unknown category: {value}") from exc
    return tuple(dict.fromkeys(result))


def is_due(last_run_at: datetime | None, interval: timedelta, now: datetime) -> bool:
    return last_run_at is None or now - last_run_at >= interval


def industry_from_tags(tags: dict[str, str]) -> str | None:
    """Human-readable industry, e.g. {'shop': 'furniture'} -> 'Retail: furniture'."""
    for key in ("shop", "amenity", "tourism", "healthcare", "office", "craft"):
        value = tags.get(key)
        if value:
            label = INDUSTRY_LABELS[key]
            return f"{label}: {value.replace('_', ' ')}"[:191]
    return None
