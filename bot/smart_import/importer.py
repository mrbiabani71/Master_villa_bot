"""
Importer — takes a parsed VillaData and writes it to PostgreSQL via the API.

Designed for extensibility:
  import_villa(data, mode="create")   → implemented
  import_villa(data, mode="update")   → stub (add _do_update when ready)
  import_villa(data, mode="upsert")   → stub (add _do_upsert when ready)

No Telegram, no channel IDs — purely storage-facing.
Villa records are stored in PostgreSQL; SQLite is not used here.
"""
from __future__ import annotations

import logging

from .models import VillaData, ImportResult, ImportMode

logger = logging.getLogger(__name__)


def import_villa(data: VillaData, mode: ImportMode = "create") -> ImportResult:
    """
    Persist a parsed villa to PostgreSQL via the local API server.

    Parameters
    ----------
    data : VillaData
        Output of parse_villa_text().  villa_code may be None (auto-assigned).
    mode : "create" | "update" | "upsert"
        • create  — insert new row; error on duplicate code  (implemented)
        • update  — update existing row by code             (stub)
        • upsert  — create or update                        (stub)

    Returns
    -------
    ImportResult with success flag, assigned villa_code, DB id, and any error.
    """
    if mode == "update":
        return _do_update(data)
    if mode == "upsert":
        return _do_upsert(data)
    return _do_create(data)


# ── create ────────────────────────────────────────────────────────────────────

def _do_create(data: VillaData) -> ImportResult:
    # Lazy import keeps this module usable without the API server running at
    # import time (mirrors the original pattern of deferring DB imports).
    from pg_villas import create_villa

    # ── 1. Build API payload ──────────────────────────────────────────────────
    document_type = "، ".join(data.documents) if data.documents else ""

    api_payload: dict = {
        "city":            data.city or "",
        "area_type":       data.area_type or "",
        "price":           data.price,
        "land_size":       data.land_size,
        "building_size":   data.building_size,
        "bedrooms":        data.bedrooms,
        "master_bedrooms": data.master_bedrooms,
        "is_townhouse":    0,
        "has_pool":        data.has_pool,
        "has_jacuzzi":     data.has_jacuzzi,
        "has_roof_garden": data.has_roof_garden,
        "has_parking":     data.has_parking,
        "has_storage":     data.has_storage,
        "document_type":   document_type,
        "description":     data.description,
        "latitude":        None,
        "longitude":       None,
        "photos":          ",".join(data.photos) if data.photos else None,
        "video":           None,
        "status":          "published",
    }
    # Include villa_code only when explicitly provided; omit it so the API
    # auto-generates the next MV-NNNN code when none is supplied.
    if data.villa_code:
        api_payload["villa_code"] = data.villa_code

    # ── 2. Create via API (handles duplicate check + DB write atomically) ─────
    try:
        created = create_villa(api_payload)
    except ValueError as exc:
        # 409 duplicate code or 400 bad data — clean, human-readable message
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


# ── update (stub) ─────────────────────────────────────────────────────────────

def _do_update(data: VillaData) -> ImportResult:
    """
    Update an existing villa by villa_code.
    Stub — implement when the Update Existing Villa workflow is ready.

    To implement:
      1. Add PUT /villas/:id support to pg_villas (or call the API directly)
      2. Build the fields dict from data (same logic as _do_create)
      3. Call the update function and return ImportResult(success=True, ...)
    """
    return ImportResult(
        success=False,
        villa_code=data.villa_code,
        mode="update",
        error="حالت update هنوز پیاده‌سازی نشده است.",
    )


# ── upsert (stub) ─────────────────────────────────────────────────────────────

def _do_upsert(data: VillaData) -> ImportResult:
    """
    Create or update based on whether villa_code already exists.
    Stub — implement once _do_update is ready.
    """
    if not data.villa_code:
        # No code → can only be a new villa
        return _do_create(data)

    from pg_villas import get_villa_by_code
    existing = get_villa_by_code(data.villa_code)
    if existing:
        return _do_update(data)
    return _do_create(data)
