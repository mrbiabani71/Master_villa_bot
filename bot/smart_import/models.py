"""
Data models shared between the parser, importer, and all future adapters.
No Telegram, no DB, no I/O — pure Python dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ImportMode = Literal["create", "update", "upsert"]


@dataclass
class VillaData:
    """Structured villa data produced by the parser."""

    # Identity
    villa_code: str | None = None       # None → importer assigns next code

    # Location
    city: str | None = None
    area_type: str | None = None        # ساحلی / جنگلی (derived from city)

    # Dimensions
    land_size: float | None = None      # m²
    building_size: float | None = None  # m²

    # Rooms
    bedrooms: int | None = None
    master_bedrooms: int | None = None

    # Price
    price: float | None = None          # Tomans (raw number)

    # Documents — list of raw strings e.g. ["سند تک برگ", "پروانه ساخت"]
    documents: list[str] = field(default_factory=list)

    # Boolean feature flags (map directly to DB columns)
    has_pool: int = 0
    has_jacuzzi: int = 0
    has_roof_garden: int = 0
    has_parking: int = 0
    has_storage: int = 0

    # Additional human-readable features (for description / display)
    features: list[str] = field(default_factory=list)

    # Free-text description (includes unrecognised lines)
    description: str = ""

    # Photo file_ids collected during the Telegram import flow
    photos: list[str] = field(default_factory=list)

    # Original raw text for audit / debugging
    raw_text: str = ""

    # ── Extended channel-import fields ───────────────────────────────────────
    # Extracted from Persian channel post text.

    region: str | None = None           # e.g. "منطقه فریدونکنار شهرک دریایی"
    villa_type: str | None = None       # e.g. "دوبلکس", "یک طبقه", "نوساز"
    facade: str | None = None           # e.g. "نمای مدرن", "سنگ و چوب"
    utilities: list[str] = field(default_factory=list)   # infrastructure lines
    location_status: str | None = None  # e.g. "کنار دریا", "مشرف به جنگل"
    community_status: str | None = None # e.g. "داخل شهرک", "خارج شهرک"

    # ── Telegram provenance ───────────────────────────────────────────────────
    # Set by the channel importer; None for manually-added villas.

    telegram_message_id: int | None = None       # message_id of the primary post
    telegram_media_group_id: str | None = None   # non-None for albums
    original_caption: str = ""                   # raw Telegram caption text


@dataclass
class ImportResult:
    """Outcome returned by importer.import_villa()."""

    success: bool
    villa_code: str | None = None   # assigned or existing code
    villa_id: int | None = None     # DB row id on success
    mode: ImportMode = "create"
    error: str | None = None        # human-readable message on failure
