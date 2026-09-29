---
name: Telegram channel import — two distinct paths
description: Why this project has two separate importers for the same Telegram channel, and which one to touch for which request.
---

This project imports villa listings from a Telegram channel through two
**intentionally separate** mechanisms — don't merge them or assume one
replaces the other:

1. **One-off/backfill history import** (`bot/channel_history/`) — uses
   Pyrogram (MTProto), which requires `TELEGRAM_API_ID` + `TELEGRAM_API_HASH`
   from my.telegram.org. Only way to fetch a channel's *full past* history,
   since the Bot API has no "get all old messages" call.
2. **Live/real-time import** (`bot/channel_importer.py`) — uses only Bot API
   `channel_post` / `edited_channel_post` updates via python-telegram-bot
   long-polling, driven by the existing `TELEGRAM_BOT_TOKEN`. No MTProto
   credentials at all. This is what the user explicitly asked for when they
   said "don't use Telethon/API_ID/API_HASH."

**Why:** the user declined to provide `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`,
so real-time-only import was built/verified as a fully separate code path
that doesn't depend on those secrets, rather than trying to make the
history importer credential-optional.

**How to apply:** both paths converge on the same idempotent upsert,
`smart_import.importer.import_villa_from_channel(data)`, keyed by
`telegram_message_id` — safe to call repeatedly (retries, restarts, edited
posts all resolve to update-in-place instead of duplicate rows). For albums,
the canonical `telegram_message_id` is the *lowest* message_id in the group
(stable across the group regardless of which message carries the caption).
If a future request touches channel import, ask which path (backfill vs.
live) before assuming.
