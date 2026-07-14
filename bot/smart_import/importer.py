"""
Importer — takes a parsed VillaData and writes it to PostgreSQL via the API.

Public API
----------
import_villa(data, mode)           → create / update / upsert by villa_code
import_villa_from_channel(data)    → idempotent upsert by telegram_message_id
                                     (falls back to create if no message_id)

No Telegram, no channel IDs — purely storage-facing.
"""
from __future__ import annotations

import logging

from .models import VillaData, ImportResult, ImportMode

logger = logging.getLogger(__name__)


# ── Public entry points ───────────────────────────────────────────────────────

def import_villa(data: VillaData, mode: ImportMode = "create") -> ImportResult:
    """
    Persist a parsed villa to PostgreSQL via the local API server.

    Parameters
    ----------
    data : VillaData
        Output of parse_villa_text().  villa_code may be None (auto-assigned).
    mode : "create" | "update" | "upsert"
        • create  — insert new row; error on duplicate code
        • update  — update existing row by code
        • upsert  — create or update by code
    """
    if mode == "update":
        return _do_update(data)
    if mode == "upsert":
        return _do_upsert(data)
    return _do_create(data)


def import_villa_from_channel(data: VillaData) -> ImportResult:
    """
    Idempotent upsert for the channel history importer.

    Lookup strategy:
      1. If telegram_message_id is set → check DB for an existing villa with
         that message_id.  If found → update it (preserving villa_code/id).
      2. If not found (or no message_id) → create a new villa.

    Safe to call repeatedly with the same data.
    """
    if data.telegram_message_id is not None:
        from pg_villas import get_villa_by_telegram_message_id
        existing = get_villa_by_telegram_message_id(data.telegram_message_id)
        if existing:
            data.villa_code = existing["villa_code"]
            # TEMP TRACE (remove after debugging telegram_message_id issue)
            logger.info(
                "TRACE-5 | final action=UPDATE existing villa id=%s telegram_message_id=%s",
                existing["id"], data.telegram_message_id,
            )
            return _do_update_by_id(existing["id"], data, existing)
    # TEMP TRACE (remove after debugging telegram_message_id issue)
    logger.info(
        "TRACE-5 | final action=CREATE (telegram_message_id=%s had no existing match)",
        data.telegram_message_id,
    )
    return _do_create(data)


# ── Payload builder ───────────────────────────────────────────────────────────

def _build_payload(data: VillaData, existing: dict | None = None) -> dict:
    """
    Build the API payload dict from VillaData.

    When *existing* is supplied (update path), fields that VillaData does not
    model (latitude, longitude, video, is_townhouse, status) are inherited
    from the existing DB row instead of being reset.
    """
    document_type = "، ".join(data.documents) if data.documents else ""
    utilities_str = "، ".join(data.utilities) if data.utilities else None

    inherit = existing or {}

    return {
        # Core property attributes
        "city":            data.city or "",
        "area_type":       data.area_type or "",
        "price":           data.price,
        "land_size":       data.land_size,
        "building_size":   data.building_size,
        "bedrooms":        data.bedrooms,
        "master_bedrooms": data.master_bedrooms,
        "is_townhouse":    inherit.get("is_townhouse", 0),
        "has_pool":        data.has_pool,
        "has_jacuzzi":     data.has_jacuzzi,
        "has_roof_garden": data.has_roof_garden,
        "has_parking":     data.has_parking,
        "has_storage":     data.has_storage,
        "document_type":   document_type,
        "description":     data.description,
        "latitude":        inherit.get("latitude"),
        "longitude":       inherit.get("longitude"),
        "photos":          ",".join(data.photos) if data.photos else None,
        "video":           inherit.get("video"),
        "status":          inherit.get("status", "published"),
        # Channel importer provenance
        "telegram_message_id":     data.telegram_message_id,
        "telegram_media_group_id": data.telegram_media_group_id,
        "original_caption":        data.original_caption or None,
        # Extended attributes
        "region":          data.region,
        "villa_type":      data.villa_type,
        "facade":          data.facade,
        "utilities":       utilities_str,
        "location_status": data.location_status,
        "community_status": data.community_status,
    }


# ── create ────────────────────────────────────────────────────────────────────

def _do_create(data: VillaData) -> ImportResult:
    from pg_villas import create_villa

    api_payload = _build_payload(data)

    # Include villa_code only when explicitly provided; omit it so the API
    # auto-generates the next MV-NNNN code when none is supplied.
    if data.villa_code:
        api_payload["villa_code"] = data.villa_code

    try:
        created = create_villa(api_payload)
    except ValueError as exc:
        return ImportResult(
            success=False,
            villa_code=data.villa_code or "",
            mode="create",
            error=str(exc),
        )
    except Exception as exc:
        logger.exception(
            "smart_import: API create failed for code=%s", data.villa_code or "(auto)"
        )
        return ImportResult(
            success=False,
            villa_code=data.villa_code or "",
            mode="create",
            error=f"خطای ذخیره‌سازی: {exc}",
        )

    villa_code = created["villa_code"]
    villa_id   = created["id"]

    logger.info(
        "smart_import: created villa code=%s id=%s city=%s price=%s",
        villa_code, villa_id, data.city, data.price,
    )
    return ImportResult(
        success=True,
        villa_code=villa_code,
        villa_id=villa_id,
        mode="create",
    )


# ── update by villa_code ──────────────────────────────────────────────────────

def _do_update(data: VillaData) -> ImportResult:
    """
    Update an existing villa by villa_code.

    Fetches the existing row to obtain the numeric id and preserve fields that
    VillaData does not model (latitude, longitude, video, is_townhouse, status).
    """
    from pg_villas import get_villa_by_code, update_villa

    if not data.villa_code:
        return ImportResult(
            success=False,
            villa_code="",
            mode="update",
            error="کد ویلا برای ویرایش الزامی است.",
        )

    existing = get_villa_by_code(data.villa_code)
    if not existing:
        return ImportResult(
            success=False,
            villa_code=data.villa_code,
            mode="update",
            error=f"ویلا با کد {data.villa_code} یافت نشد.",
        )

    return _do_update_by_id(existing["id"], data, existing)


# ── update by database id ─────────────────────────────────────────────────────

def _do_update_by_id(
    villa_id: int,
    data: VillaData,
    existing: dict | None = None,
) -> ImportResult:
    """
    Update a villa by its DB id (caller already has the id — avoids an extra
    round-trip).  *existing* is passed to inherit unmodelled fields.
    """
    from pg_villas import update_villa

    api_payload = _build_payload(data, existing)

    try:
        updated = update_villa(villa_id, api_payload)
    except ValueError as exc:
        return ImportResult(
            success=False,
            villa_code=data.villa_code,
            mode="update",
            error=str(exc),
        )
    except Exception as exc:
        logger.exception(
            "smart_import: API update failed id=%s code=%s", villa_id, data.villa_code
        )
        return ImportResult(
            success=False,
            villa_code=data.villa_code,
            mode="update",
            error=f"خطای ذخیره‌سازی: {exc}",
        )

    logger.info(
        "smart_import: updated villa code=%s id=%s city=%s price=%s",
        data.villa_code, villa_id, data.city, data.price,
    )
    return ImportResult(
        success=True,
        villa_code=data.villa_code,
        villa_id=villa_id,
        mode="update",
    )


# ── upsert by villa_code ──────────────────────────────────────────────────────

def _do_upsert(data: VillaData) -> ImportResult:
    """Create or update based on whether villa_code already exists."""
    if not data.villa_code:
        # No code → can only be a new villa
        return _do_create(data)

    from pg_villas import get_villa_by_code
    existing = get_villa_by_code(data.villa_code)
    if existing:
        return _do_update_by_id(existing["id"], data, existing)
    return _do_create(data)
