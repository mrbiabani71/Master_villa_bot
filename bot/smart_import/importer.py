"""
Importer — takes a parsed VillaData and writes it to the database.

Designed for extensibility:
  import_villa(data, mode="create")   → implemented
  import_villa(data, mode="update")   → stub (add _do_update when ready)
  import_villa(data, mode="upsert")   → stub (add _do_upsert when ready)

No Telegram, no channel IDs — purely DB-facing.
"""
from __future__ import annotations

import logging

from .models import VillaData, ImportResult, ImportMode

logger = logging.getLogger(__name__)


def import_villa(data: VillaData, mode: ImportMode = "create") -> ImportResult:
    """
    Persist a parsed villa to the database.

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
    # Import here to keep this module importable without a running DB
    from database import get_next_villa_code, get_villa_by_code, insert_villa

    # ── 1. Resolve villa code ─────────────────────────────────────────────────
    if data.villa_code:
        # Provided by text: check for duplicates
        existing = get_villa_by_code(data.villa_code)
        if existing:
            return ImportResult(
                success=False,
                villa_code=data.villa_code,
                mode="create",
                error=f"کد ویلا {data.villa_code} قبلاً ثبت شده است.",
            )
        villa_code = data.villa_code
    else:
        # Auto-generate
        villa_code = get_next_villa_code()

    # ── 2. Build DB row ───────────────────────────────────────────────────────
    # Join documents list → single string for document_type column
    document_type = "، ".join(data.documents) if data.documents else ""

    db_data: dict = {
        "villa_code":     villa_code,
        "city":           data.city or "",
        "area_type":      data.area_type or "",
        "price":          data.price,
        "land_size":      data.land_size,
        "building_size":  data.building_size,
        "bedrooms":       data.bedrooms,
        "master_bedrooms": data.master_bedrooms,
        "is_townhouse":   0,
        "has_pool":       data.has_pool,
        "has_jacuzzi":    data.has_jacuzzi,
        "has_roof_garden": data.has_roof_garden,
        "has_parking":    data.has_parking,
        "has_storage":    data.has_storage,
        "document_type":  document_type,
        "description":    data.description,
        "latitude":       None,
        "longitude":      None,
        "photos":         [],
        "video":          None,
    }

    # ── 3. Insert ─────────────────────────────────────────────────────────────
    try:
        villa_id = insert_villa(db_data)
    except Exception as exc:
        logger.exception("smart_import: DB insert failed for code=%s", villa_code)
        return ImportResult(
            success=False,
            villa_code=villa_code,
            mode="create",
            error=f"خطای پایگاه داده: {exc}",
        )

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
      1. Add update_villa(villa_code, fields: dict) to database.py
      2. Build the fields dict from data (same logic as _do_create)
      3. Call update_villa and return ImportResult(success=True, ...)
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

    from database import get_villa_by_code
    existing = get_villa_by_code(data.villa_code)
    if existing:
        return _do_update(data)
    return _do_create(data)
