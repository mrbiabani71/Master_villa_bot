"""
Villa lookups backed by PostgreSQL via the local API server.

Drop-in replacements for search_villas / get_villa_by_id / get_villa_by_code
used by the user-facing browse and visit flows.

No database credentials required — all reads go through
http://localhost:3000/api, which owns the PostgreSQL connection.
SQLite (bot.db) is deliberately NOT used here.
"""
from __future__ import annotations

import logging

import httpx

API_BASE   = "http://localhost:3000/api"
_PAGE_SIZE = 100          # comfortably above the expected villa count

logger = logging.getLogger(__name__)


def _get(path: str, **params: object) -> dict | None:
    """GET {API_BASE}{path} with optional query params; return parsed JSON or None."""
    clean = {k: v for k, v in params.items() if v is not None}
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{API_BASE}{path}", params=clean)
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        logger.error("pg_villas | API error GET %s params=%s: %s", path, clean, exc)
        return None


def search_villas(
    area_type: str,
    min_price: float,
    max_price: float | None,
    city: str | None = None,
) -> list[dict]:
    """
    Return published villas matching area_type and price range, ordered by
    price ASC then id DESC (mirrors the original SQLite query order).

    Price filtering is applied client-side because the API does not expose
    price-range query params.
    """
    result = _get(
        "/villas",
        status="published",
        area_type=area_type,
        city=city,
        page=0,
        page_size=_PAGE_SIZE,
    )
    if not result:
        return []

    rows: list[dict] = result.get("data", [])

    filtered = []
    for v in rows:
        price = v.get("price")
        if price is None:
            continue
        if price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        filtered.append(v)

    filtered.sort(key=lambda v: (v.get("price") or 0, -(v.get("id") or 0)))
    return filtered


def get_villa_by_id(villa_id: int) -> dict | None:
    """Fetch a single villa by its numeric database id."""
    result = _get(f"/villas/{villa_id}")
    return result if isinstance(result, dict) and "id" in result else None


def get_villa_by_code(villa_code: str) -> dict | None:
    """
    Fetch a single villa by MV code.

    The API does not support villa_code filtering, so we fetch the full
    published+draft list and match client-side.  Villa counts are small
    (<100) so this is acceptable.
    """
    result = _get("/villas", page=0, page_size=_PAGE_SIZE)
    if not result:
        return None
    for v in result.get("data", []):
        if v.get("villa_code") == villa_code:
            return v
    return None
