"""
Small test import — fetches the latest 20 raw channel messages via Pyrogram,
groups them using the existing collector logic, caps the run at the 10 most
recent groups, then imports them through the existing pipeline.

Does NOT modify any importer logic.  Safe to re-run (idempotent upserts).

Usage (from the project root):
    python3 bot/channel_history/_test_import.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BOT_ROOT  = os.path.dirname(_THIS_DIR)
for _p in (_BOT_ROOT, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_import")

RAW_FETCH_LIMIT = 20   # raw messages to pull from Telegram
GROUP_CAP       = 10   # max villa groups to import


async def main() -> None:
    # ── 1. Validate env vars ──────────────────────────────────────────────────
    bot_token      = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_id_str     = os.environ.get("TELEGRAM_API_ID", "")
    api_hash       = os.environ.get("TELEGRAM_API_HASH", "")
    channel_id_str = os.environ.get("CHANNEL_ID", "")

    missing = [n for n, v in [
        ("TELEGRAM_BOT_TOKEN", bot_token),
        ("TELEGRAM_API_ID",    api_id_str),
        ("TELEGRAM_API_HASH",  api_hash),
        ("CHANNEL_ID",         channel_id_str),
    ] if not v]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    api_id     = int(api_id_str)
    channel_id = int(channel_id_str)

    # ── 2. Check API server ───────────────────────────────────────────────────
    import httpx
    api_port = os.environ.get("API_SERVER_PORT", "8080")
    health_url = f"http://localhost:{api_port}/api/healthz"
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(health_url)
            r.raise_for_status()
        print(f"✅ API server reachable at {health_url}")
    except Exception as exc:
        print(f"❌ API server not reachable at {health_url}: {exc}")
        sys.exit(1)

    # ── 3. Fetch latest N raw messages via Pyrogram (in-memory session) ───────
    # Pyrogram 2.0.106 hard-codes MIN_CHANNEL_ID = -1002147483647 (old 32-bit cap).
    # Our channel ID 4187733480 exceeds that, causing "Peer id invalid".
    # Patch the constant before any Pyrogram peer resolution runs.
    import pyrogram.utils as _pyu
    _pyu.MIN_CHANNEL_ID = -1009999999999999

    from pyrogram import Client
    from channel_history.collector import _group_messages  # existing private fn

    # Use the same persistent session as collector.py so the channel peer is
    # resolved and cached (in-memory sessions can't resolve numeric channel IDs).
    session_name = "channel_history_bot"
    workdir      = _BOT_ROOT

    print(f"\nFetching latest {RAW_FETCH_LIMIT} messages from channel {channel_id}…")
    print(f"  Session: {workdir}/{session_name}.session")
    raw_messages: list = []
    async with Client(
        session_name,
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token,
        workdir=workdir,
    ) as app:
        async for msg in app.get_chat_history(channel_id, limit=RAW_FETCH_LIMIT):
            raw_messages.append(msg)

    print(f"  Raw messages fetched : {len(raw_messages)}")

    # get_chat_history returns newest-first → sort chronological for grouper
    raw_messages.sort(key=lambda m: m.id)

    # ── 4. Group into VillaGroups (existing logic, unmodified) ───────────────
    all_groups = _group_messages(raw_messages)
    print(f"  Villa groups found   : {len(all_groups)}")

    # Cap to most recent GROUP_CAP groups
    groups = all_groups[-GROUP_CAP:]
    print(f"  Groups to import     : {len(groups)}  (capped at {GROUP_CAP})")

    if not groups:
        print("\nNo importable groups found in the last messages — nothing to import.")
        return

    # ── 5. Print group preview ────────────────────────────────────────────────
    print("\n── Group preview ─────────────────────────────────────────────────")
    for i, g in enumerate(groups):
        caption_preview = (g.text[:60] + "…") if len(g.text) > 60 else g.text
        caption_preview = caption_preview.replace("\n", " ")
        print(
            f"  [{i+1:2d}] msg_id={g.telegram_message_id:<8}  "
            f"photos={len(g.photo_file_ids)}  "
            f"album={'yes' if g.telegram_media_group_id else 'no ':3}  "
            f"text={bool(g.text)!s:<5}  "
            f"caption: {caption_preview!r}"
        )

    # ── 6. Import via existing pipeline (unmodified) ──────────────────────────
    from channel_history.importer import import_villa_groups

    print("\n── Importing… ────────────────────────────────────────────────────")
    results = await import_villa_groups(groups)

    # ── 7. Summary ────────────────────────────────────────────────────────────
    created  = [r for r in results if r.success and r.mode == "create"]
    updated  = [r for r in results if r.success and r.mode == "update"]
    failed   = [r for r in results if not r.success]
    skipped  = len(groups) - len(results)

    print("\n══════════════════════════════════════════════════════════════════")
    print("  Test Import Summary")
    print("══════════════════════════════════════════════════════════════════")
    print(f"  Messages checked   : {len(raw_messages)}")
    print(f"  Groups formed      : {len(all_groups)}  (imported last {len(groups)})")
    print(f"  ✅ New villas      : {len(created)}")
    for r in created:
        print(f"       code={r.villa_code}  id={r.villa_id}")
    print(f"  🔄 Updated villas  : {len(updated)}")
    for r in updated:
        print(f"       code={r.villa_code}  id={r.villa_id}")
    print(f"  ⏭  Skipped (no text): {skipped}")
    print(f"  ❌ Failed          : {len(failed)}")
    for r in failed:
        print(f"       code={r.villa_code}  error={r.error}")

    # ── 8. Photo / caption coverage ──────────────────────────────────────────
    groups_with_photos   = sum(1 for g in groups if g.photo_file_ids)
    groups_with_captions = sum(1 for g in groups if g.text)
    groups_albums        = sum(1 for g in groups if g.telegram_media_group_id)
    print(f"\n  Photos handled     : {groups_with_photos}/{len(groups)} groups had photos")
    print(f"  Captions handled   : {groups_with_captions}/{len(groups)} groups had text")
    print(f"  Albums (multi-photo): {groups_albums}/{len(groups)} groups were albums")
    print("══════════════════════════════════════════════════════════════════")

    if failed:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
