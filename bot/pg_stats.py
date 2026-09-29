"""
Stats helpers — thin wrappers around the two stats endpoints.

  get_villa_stats()    → GET /api/villas/stats
  get_request_stats()  → GET /api/requests/stats

Both return a plain dict on success or None on any error.
"""
from __future__ import annotations

import logging
import httpx

API_BASE = "http://localhost:3000/api"
logger   = logging.getLogger(__name__)


def _get(path: str) -> dict | None:
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{API_BASE}{path}")
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        logger.error("pg_stats | GET %s failed: %s", path, exc)
        return None


def get_villa_stats() -> dict | None:
    """
    Returns:
      total, published, inactive, draft, sold, archived,
      by_city      [ {city, count} … ],
      by_area_type [ {area_type, count} … ],
      by_price_tier[ {tier, count} … ],
      latest_import  ISO-8601 string or null
    """
    return _get("/villas/stats")


def get_request_stats() -> dict | None:
    """
    Returns:
      total, pending, contacted, visit_count, consultation_count
    """
    return _get("/requests/stats")
