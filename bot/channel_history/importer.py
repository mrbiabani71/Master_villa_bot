"""
Channel history importer — orchestrates the parse → upsert pipeline for a
list of VillaGroups collected by collector.py.

Each group is:
  1. Parsed with smart_import.parser.parse_villa_text
  2. Enriched with Telegram provenance (message_id, media_group_id, caption)
  3. Upserted via smart_import.importer.import_villa_from_channel
     (idempotent: same telegram_message_id → update, new → create)

Groups with no text are skipped silently (nothing to parse).
"""
from __future__ import annotations

import logging
import os
import sys

# Allow imports from the bot/ root when this module is run directly.
_BOT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BOT_ROOT not in sys.path:
    sys.path.insert(0, _BOT_ROOT)

from smart_import.parser import parse_villa_text
from smart_import.importer import import_villa_from_channel
from smart_import.models import ImportResult
from .collector import VillaGroup

logger = logging.getLogger(__name__)


async def import_villa_groups(groups: list[VillaGroup]) -> list[ImportResult]:
    """
    Import a list of VillaGroups, returning one ImportResult per group
    (skipped groups are not included in the output list).

    This function is async so that callers (run.py) can use ``await``,
    though the underlying API calls are synchronous (httpx sync client).
    """
    results: list[ImportResult] = []

    for idx, group in enumerate(groups):
        if not group.text:
            logger.debug(
                "Group %d (msg_id=%d, album=%s): no text — skipped",
                idx, group.telegram_message_id, group.telegram_media_group_id,
            )
            continue

        # ── 1. Parse ─────────────────────────────────────────────────────────
        data = parse_villa_text(group.text)

        # ── 2. Attach Telegram provenance ────────────────────────────────────
        data.photos                  = list(group.photo_file_ids)
        data.telegram_message_id     = group.telegram_message_id
        data.telegram_media_group_id = group.telegram_media_group_id
        data.original_caption        = group.original_caption

        # ── 3. Upsert ────────────────────────────────────────────────────────
        result = import_villa_from_channel(data)

        if result.success:
            logger.info(
                "Group %d (msg_id=%d): %-6s villa %s  city=%s  price=%s  photos=%d",
                idx,
                group.telegram_message_id,
                result.mode,
                result.villa_code,
                data.city or "—",
                f"{(data.price or 0) / 1e9:.2f}B" if data.price else "—",
                len(group.photo_file_ids),
            )
        else:
            logger.warning(
                "Group %d (msg_id=%d): FAILED — %s",
                idx, group.telegram_message_id, result.error,
            )

        results.append(result)

    return results
