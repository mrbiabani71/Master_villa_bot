"""
channel_history — standalone service that reads the complete channel history
via Pyrogram (MTProto) and imports villas into PostgreSQL idempotently.

Usage (from project root):
    python3 bot/channel_history/run.py

Required env vars:
    TELEGRAM_BOT_TOKEN   — bot token (already set as Replit Secret)
    TELEGRAM_API_ID      — API ID from my.telegram.org
    TELEGRAM_API_HASH    — API hash from my.telegram.org
    CHANNEL_ID           — numeric channel ID (e.g. -1001234567890)

Public API:
    from channel_history.collector import collect_channel_history, VillaGroup
    from channel_history.importer  import import_villa_groups
"""
