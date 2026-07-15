"""
Version 1 rule-based Persian "smart search" parser.

No AI/NLP model or external service is used — this module extracts search
filters from free-form Persian text using plain regex/keyword matching. The
extracted filters are handed to the exact same ``advanced_search_villas``
function (and result rendering) already used by the category search, so both
paths run identical, unmodified search logic — this module only produces the
filter dict.

Extraction targets: region, city, price range (min/max), bedrooms, master
bedrooms, pool, jacuzzi, roof garden, parking, document status, and gated
community. Anything not recognized in the text is left unset (None/False),
matching the "optional filter" semantics of the category search — only
region and price are treated as required by the caller.
"""
from __future__ import annotations

import re

from pg_villas import _DOCUMENT_KEYWORDS

REGION_CITIES: dict[str, list[str]] = {
    "ساحلی": ["محمودآباد", "ایزدشهر", "سرخرود"],
    "جنگلی": ["نور", "آمل", "چمستان"],
}
CITY_TO_REGION = {city: region for region, cities in REGION_CITIES.items() for city in cities}

REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "جنگلی": ("جنگلی", "جنگل"),
    "ساحلی": ("ساحلی", "ساحل"),
}

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

_UNIT_MULTIPLIER = {"میلیارد": 1_000_000_000, "میلیون": 1_000_000}

# Order matters: range → max-only → min-only → bare number (ambiguous, treated as a ceiling).
_RANGE_RE = re.compile(
    r"(?:بین|از)\s*(?P<lo>\d+(?:\.\d+)?)\s*(?P<lo_unit>میلیارد|میلیون)?\s*تا\s*"
    r"(?P<hi>\d+(?:\.\d+)?)\s*(?P<hi_unit>میلیارد|میلیون)"
)
_MAX_RE = re.compile(
    r"(?:تا|زیر|کمتر از|حداکثر)\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>میلیارد|میلیون)"
)
_MIN_RE = re.compile(
    r"(?:بالای|بیشتر از|حداقل|از)\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>میلیارد|میلیون)"
)
_BARE_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>میلیارد|میلیون)")

_MASTER_BED_RE_A = re.compile(r"(\d+)\s*مستر\s*خواب")
_MASTER_BED_RE_B = re.compile(r"مستر\s*خواب\D{0,3}(\d+)")
_MASTER_BED_WORD_RE = re.compile(r"مستر\s*خواب")

_BEDROOM_RE = re.compile(r"(\d+)\s*(?:اتاق\s*)?خواب")

_ROOF_GARDEN_KEYWORDS = ("روف گاردن", "روف‌گاردن", "روفگاردن")


def _normalize_digits(text: str) -> str:
    return text.translate(_DIGIT_MAP)


def _parse_price(text: str) -> tuple[float | None, float | None]:
    m = _RANGE_RE.search(text)
    if m:
        lo_unit = m.group("lo_unit") or m.group("hi_unit")
        hi_unit = m.group("hi_unit")
        lo = float(m.group("lo")) * _UNIT_MULTIPLIER[lo_unit]
        hi = float(m.group("hi")) * _UNIT_MULTIPLIER[hi_unit]
        return (min(lo, hi), max(lo, hi))

    m = _MAX_RE.search(text)
    if m:
        return (None, float(m.group("num")) * _UNIT_MULTIPLIER[m.group("unit")])

    m = _MIN_RE.search(text)
    if m:
        return (float(m.group("num")) * _UNIT_MULTIPLIER[m.group("unit")], None)

    m = _BARE_RE.search(text)
    if m:
        return (None, float(m.group("num")) * _UNIT_MULTIPLIER[m.group("unit")])

    return (None, None)


def _parse_bedrooms(text: str) -> tuple[int | None, int | None]:
    """Returns (bedrooms, master_bedrooms). Master-bedroom mentions are
    matched and stripped first so they never get double-counted as plain
    bedrooms."""
    master = None
    m = _MASTER_BED_RE_A.search(text) or _MASTER_BED_RE_B.search(text)
    if m:
        master = int(m.group(1))
        text = text[: m.start()] + text[m.end():]
    elif _MASTER_BED_WORD_RE.search(text):
        master = 1
        text = _MASTER_BED_WORD_RE.sub("", text)

    bedrooms = None
    m = _BEDROOM_RE.search(text)
    if m:
        bedrooms = int(m.group(1))

    return bedrooms, master


def _parse_region_city(text: str) -> tuple[str | None, str | None]:
    city = None
    for c in CITY_TO_REGION:
        if c in text:
            city = c
            break

    region = None
    for r, keywords in REGION_KEYWORDS.items():
        if any(k in text for k in keywords):
            region = r
            break

    if region is None and city is not None:
        region = CITY_TO_REGION[city]

    return region, city


def parse_smart_query(raw_text: str) -> dict:
    """
    Parse free-form Persian villa-search text into a filter dict.

    Returned dict keys (each may be None/False if not mentioned in the text):
      region, city, min_price, max_price, bedrooms, master_bedrooms,
      pool, jacuzzi, roof_garden, parking, gated, document
    """
    text = _normalize_digits(raw_text or "").strip()

    region, city = _parse_region_city(text)
    min_price, max_price = _parse_price(text)
    bedrooms, master_bedrooms = _parse_bedrooms(text)

    document = None
    for doc_key, keywords in _DOCUMENT_KEYWORDS.items():
        if any(k in text for k in keywords):
            document = doc_key
            break

    return {
        "region": region,
        "city": city,
        "min_price": min_price,
        "max_price": max_price,
        "bedrooms": bedrooms,
        "master_bedrooms": master_bedrooms,
        "pool": "استخر" in text,
        "jacuzzi": "جکوزی" in text,
        "roof_garden": any(k in text for k in _ROOF_GARDEN_KEYWORDS),
        "parking": "پارکینگ" in text,
        "gated": "شهرک" in text,
        "document": document,
    }
