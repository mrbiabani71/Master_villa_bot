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
import os
import time

import httpx

API_BASE   = f"http://localhost:{os.environ.get('API_SERVER_PORT', '8080')}/api"
_PAGE_SIZE = 100          # comfortably above the expected villa count

logger = logging.getLogger(__name__)

# ── Rate-limit handling ────────────────────────────────────────────────────────
# The API enforces 60 requests / 60 s.  During a bulk channel import every
# villa costs one GET (existence check) + one POST/PUT (write), so we pace
# write operations at ≥ 1 s apart and retry automatically on 429.
_WRITE_PACING_DELAY = 1.0          # seconds between consecutive write requests
_MAX_RETRIES        = 4            # up to 5 total attempts (1 original + 4 retries)
_RETRY_BACKOFF      = (5, 15, 30, 60)  # wait per retry (seconds); last matches window


def _execute_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    """
    Execute a write (POST / PUT) HTTP request with:
    - a small upfront pacing delay to stay below the rate limit during bulk imports
    - automatic retry on HTTP 429, honouring ``retry_after_seconds`` from the
      response body and falling back to progressive back-off

    On persistent 429 after all retries, raises ``RuntimeError`` so the caller
    records it as a failed item (retrying the import later will pick it up).
    """
    time.sleep(_WRITE_PACING_DELAY)   # pace writes; keeps bulk import ≤ 60/min

    for attempt in range(_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=10) as client:
                r = getattr(client, method)(url, **kwargs)
        except Exception as exc:
            raise RuntimeError(f"Network error on {method.upper()} {url}: {exc}") from exc

        if r.status_code != 429:
            return r                  # success or a non-rate-limit error — let caller handle

        if attempt >= _MAX_RETRIES:
            break                     # exhausted — fall through to the RuntimeError below

        # Determine how long to wait
        try:
            wait: float = float(r.json().get("retry_after_seconds") or _RETRY_BACKOFF[attempt])
        except Exception:
            wait = float(_RETRY_BACKOFF[attempt])

        logger.warning(
            "pg_villas | 429 rate-limited %s %s — waiting %.0fs (attempt %d/%d)",
            method.upper(), url, wait, attempt + 1, _MAX_RETRIES,
        )
        time.sleep(wait)

    raise RuntimeError(
        f"Rate limit still active after {_MAX_RETRIES} retries "
        f"on {method.upper()} {url} — mark as failed and retry later"
    )


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


_DOCUMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tak_barg": ("تک برگ", "تک‌برگ", "تگ برگ"),
    "parvaneh": ("پروانه",),
}


def advanced_search_villas(
    area_type: str,
    min_price: float,
    max_price: float | None,
    city: str | None = None,
    bedrooms: int | None = None,
    master_bedrooms: int | None = None,
    has_pool: bool = False,
    has_jacuzzi: bool = False,
    has_roof_garden: bool = False,
    has_parking: bool = False,
    gated_community: bool = False,
    document: str | None = None,
) -> list[dict]:
    """
    Guided advanced search: region + optional city + price range + optional
    amenity/room/document/community filters.  Published villas only.

    ``bedrooms`` / ``master_bedrooms`` are treated as a minimum threshold
    (e.g. bedrooms=3 matches villas with 3 or more bedrooms).

    ``document`` is one of the keys in ``_DOCUMENT_KEYWORDS`` ("tak_barg" or
    "parvaneh"); matching is a case-sensitive substring check against the
    free-text ``document_type`` field, since that data is not normalized.

    ``gated_community`` matches villas whose ``community_status`` mentions
    "شهرک" (inside a gated community / complex).

    All filtering happens client-side, mirroring ``search_villas`` — the API
    only exposes status/area_type/city as query params.
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
    doc_keywords = _DOCUMENT_KEYWORDS.get(document or "", None)

    filtered = []
    for v in rows:
        price = v.get("price")
        if price is None:
            continue
        if price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if bedrooms is not None and (v.get("bedrooms") or 0) < bedrooms:
            continue
        if master_bedrooms is not None and (v.get("master_bedrooms") or 0) < master_bedrooms:
            continue
        if has_pool and not v.get("has_pool"):
            continue
        if has_jacuzzi and not v.get("has_jacuzzi"):
            continue
        if has_roof_garden and not v.get("has_roof_garden"):
            continue
        if has_parking and not v.get("has_parking"):
            continue
        if gated_community and "شهرک" not in (v.get("community_status") or ""):
            continue
        if doc_keywords and not any(k in (v.get("document_type") or "") for k in doc_keywords):
            continue
        filtered.append(v)

    filtered.sort(key=lambda v: (v.get("price") or 0, -(v.get("id") or 0)))
    return filtered


def get_villa_by_id(villa_id: int) -> dict | None:
    """Fetch a single villa by its numeric database id."""
    result = _get(f"/villas/{villa_id}")
    return result if isinstance(result, dict) and "id" in result else None


def get_villa_by_telegram_message_id(telegram_message_id: int) -> dict | None:
    """
    Fetch a single villa by its Telegram message ID.

    Uses the telegram_message_id filter added to GET /api/villas.
    Returns None if no matching villa is found or the API is unreachable.
    """
    result = _get("/villas", telegram_message_id=telegram_message_id, page=0, page_size=1)
    if not result:
        return None
    rows: list[dict] = result.get("data", [])
    return rows[0] if rows else None


def create_villa(data: dict) -> dict:
    """
    Create a new villa via POST /api/villas.

    ``data`` must contain at minimum the fields required by the API schema
    (city, area_type, price …).  An optional ``villa_code`` key may be
    included; the API will use it as-is or auto-generate one if omitted.

    Returns the created villa dict on success (HTTP 201).
    Raises ``ValueError`` on 400 (invalid data) or 409 (duplicate villa_code).
    Raises ``RuntimeError`` on network failures or unexpected HTTP responses.
    """
    try:
        r = _execute_with_retry("post", f"{API_BASE}/villas", json=data)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.error("pg_villas | network error POST /villas: %s", exc)
        raise RuntimeError(f"Network error while creating villa: {exc}") from exc

    if r.status_code == 201:
        return r.json()

    # 200 means ON CONFLICT DO NOTHING fired — the row already exists.
    # The API returns the existing villa so callers can read its id/code.
    if r.status_code == 200:
        return r.json()

    # Surface clean errors for known status codes
    try:
        body = r.json()
        message = body.get("error") or str(body)
    except Exception:
        message = r.text or f"HTTP {r.status_code}"

    if r.status_code == 409:
        raise ValueError(f"Duplicate villa code: {message}")
    if r.status_code == 400:
        raise ValueError(f"Invalid villa data: {message}")

    logger.error("pg_villas | unexpected %s from POST /villas: %s", r.status_code, message)
    raise RuntimeError(f"API error {r.status_code}: {message}")


def update_villa(villa_id: int, data: dict) -> dict:
    """
    Update an existing villa via PUT /api/villas/:id.

    ``data`` must contain all writable fields (same shape as create payload).
    Returns the updated villa dict on success (HTTP 200).
    Raises ``ValueError`` on 400 (invalid data) or 404 (not found).
    Raises ``RuntimeError`` on network failures or unexpected HTTP responses.
    """
    try:
        r = _execute_with_retry("put", f"{API_BASE}/villas/{villa_id}", json=data)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.error("pg_villas | network error PUT /villas/%s: %s", villa_id, exc)
        raise RuntimeError(f"Network error while updating villa: {exc}") from exc

    if r.status_code == 200:
        return r.json()

    try:
        body = r.json()
        message = body.get("error") or str(body)
    except Exception:
        message = r.text or f"HTTP {r.status_code}"

    if r.status_code == 404:
        raise ValueError(f"Villa not found: {message}")
    if r.status_code == 400:
        raise ValueError(f"Invalid villa data: {message}")

    logger.error("pg_villas | unexpected %s from PUT /villas/%s: %s", r.status_code, villa_id, message)
    raise RuntimeError(f"API error {r.status_code}: {message}")


def admin_search_villas(
    code: str | None = None,
    city: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Fetch ALL villas (every status) for the admin management panel.

    Filtering is applied client-side:
      code      — partial match on villa_code (case-insensitive)
      city      — partial match on city name
      max_price — inclusive upper bound on price (in Tomans)

    Pass no arguments to return the full villa list.
    """
    result = _get("/villas", page=0, page_size=_PAGE_SIZE)
    if not result:
        return []
    rows: list[dict] = result.get("data", [])

    if code:
        code_upper = code.upper()
        rows = [v for v in rows if code_upper in (v.get("villa_code") or "").upper()]

    if city:
        rows = [v for v in rows if city in (v.get("city") or "")]

    if max_price is not None:
        rows = [v for v in rows if (v.get("price") or 0) <= max_price]

    return rows


def delete_villa(villa_id: int) -> bool:
    """
    Permanently delete a villa row from the database via
    DELETE /api/villas/:id/hard.

    Returns True on success, False on any error.
    """
    try:
        with httpx.Client(timeout=10) as client:
            r = client.delete(f"{API_BASE}/villas/{villa_id}/hard")
        if r.status_code == 200:
            return True
        logger.error(
            "pg_villas | delete_villa(%s) → HTTP %s: %s",
            villa_id, r.status_code, r.text,
        )
        return False
    except Exception as exc:
        logger.error("pg_villas | network error DELETE /villas/%s/hard: %s", villa_id, exc)
        return False


def set_villa_status(villa_id: int, status: str) -> bool:
    """
    Update a villa's status via PATCH /api/villas/:id.

    ``status`` must be one of: draft, published, sold, archived, inactive.
    Returns True on success, False on any error.
    """
    try:
        with httpx.Client(timeout=10) as client:
            r = client.patch(f"{API_BASE}/villas/{villa_id}", json={"status": status})
        if r.status_code == 200:
            return True
        logger.error(
            "pg_villas | set_villa_status(%s, %s) → HTTP %s: %s",
            villa_id, status, r.status_code, r.text,
        )
        return False
    except Exception as exc:
        logger.error("pg_villas | network error PATCH /villas/%s: %s", villa_id, exc)
        return False


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
