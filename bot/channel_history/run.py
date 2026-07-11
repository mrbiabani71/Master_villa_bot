"""
Channel History Importer — entry point.

Reads the complete history of the configured Telegram channel and upserts
every villa post into PostgreSQL.  Safe to run multiple times (idempotent).

Usage (from the project root):
    python3 bot/channel_history/run.py

Required environment variables:
    TELEGRAM_BOT_TOKEN   — already set as Replit Secret
    TELEGRAM_API_ID      — integer API ID from https://my.telegram.org
    TELEGRAM_API_HASH    — string API hash from https://my.telegram.org
    CHANNEL_ID           — numeric channel ID (e.g. -1001234567890)

Optional:
    LOG_LEVEL            — DEBUG / INFO (default) / WARNING
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
# Support both:
#   python3 bot/channel_history/run.py      (from project root)
#   python3 -m channel_history.run          (from bot/ directory)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BOT_ROOT  = os.path.dirname(_THIS_DIR)
for _p in (_BOT_ROOT, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Logging ───────────────────────────────────────────────────────────────────
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("channel_history.run")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    # ── Validate required env vars ────────────────────────────────────────────
    bot_token  = os.environ.get("TELEGRAM_BOT_TOKEN")
    api_id_str = os.environ.get("TELEGRAM_API_ID")
    api_hash   = os.environ.get("TELEGRAM_API_HASH")
    channel_id_str = os.environ.get("CHANNEL_ID")

    missing = [
        name for name, val in [
            ("TELEGRAM_BOT_TOKEN", bot_token),
            ("TELEGRAM_API_ID",    api_id_str),
            ("TELEGRAM_API_HASH",  api_hash),
            ("CHANNEL_ID",         channel_id_str),
        ]
        if not val
    ]
    if missing:
        logger.error(
            "Missing required environment variables: %s\n"
            "  TELEGRAM_API_ID and TELEGRAM_API_HASH → https://my.telegram.org\n"
            "  CHANNEL_ID → numeric channel ID (e.g. -1001234567890)",
            ", ".join(missing),
        )
        sys.exit(1)

    try:
        api_id     = int(api_id_str)  # type: ignore[arg-type]
        channel_id = int(channel_id_str)  # type: ignore[arg-type]
    except ValueError as exc:
        logger.error("TELEGRAM_API_ID and CHANNEL_ID must be integers: %s", exc)
        sys.exit(1)

    # ── Check API server is reachable before starting ─────────────────────────
    import httpx
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get("http://localhost:3000/api/healthz")
            r.raise_for_status()
    except Exception as exc:
        logger.error(
            "API server is not reachable at http://localhost:3000/api/healthz\n"
            "Make sure the API Server workflow is running before importing.\n"
            "Error: %s", exc,
        )
        sys.exit(1)

    # ── Step 1: Collect channel history ──────────────────────────────────────
    from channel_history.collector import collect_channel_history

    logger.info("═" * 60)
    logger.info("Channel History Importer starting")
    logger.info("Channel: %s", channel_id)
    logger.info("═" * 60)

    groups = await collect_channel_history(
        bot_token=bot_token,  # type: ignore[arg-type]
        api_id=api_id,
        api_hash=api_hash,
        channel_id=channel_id,
    )

    if not groups:
        logger.info("No messages found in channel — nothing to import.")
        return

    logger.info("Collected %d villa groups — starting import…", len(groups))

    # ── Step 2: Import / upsert ───────────────────────────────────────────────
    from channel_history.importer import import_villa_groups

    results = await import_villa_groups(groups)

    # ── Step 3: Summary ───────────────────────────────────────────────────────
    created  = sum(1 for r in results if r.success and r.mode == "create")
    updated  = sum(1 for r in results if r.success and r.mode == "update")
    failed   = sum(1 for r in results if not r.success)
    skipped  = len(groups) - len(results)

    logger.info("═" * 60)
    logger.info("Import complete")
    logger.info("  ✅ Created : %d", created)
    logger.info("  🔄 Updated : %d", updated)
    logger.info("  ❌ Failed  : %d", failed)
    logger.info("  ⏭  Skipped : %d  (no text)", skipped)
    logger.info("  📦 Total   : %d", len(groups))
    logger.info("═" * 60)

    if failed:
        logger.warning("%d groups failed to import — check logs above for details.", failed)
        sys.exit(2)   # non-zero exit so CI/scripts can detect partial failures


if __name__ == "__main__":
    asyncio.run(main())
