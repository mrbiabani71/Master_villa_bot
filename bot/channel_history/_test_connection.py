"""
Connection test — verifies TELEGRAM_API_ID / TELEGRAM_API_HASH are readable
and that Pyrogram can authenticate with Telegram.  Does NOT fetch any messages.

Run from the project root:
    python3 bot/channel_history/_test_connection.py
"""
from __future__ import annotations

import asyncio
import os
import sys

_BOT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BOT_ROOT not in sys.path:
    sys.path.insert(0, _BOT_ROOT)


async def main() -> None:
    # ── 1. Read env vars ──────────────────────────────────────────────────────
    bot_token  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_id_str = os.environ.get("TELEGRAM_API_ID", "")
    api_hash   = os.environ.get("TELEGRAM_API_HASH", "")

    print("── Environment variables ─────────────────────────────────────────")
    print(f"  TELEGRAM_BOT_TOKEN : {'✅ set' if bot_token  else '❌ MISSING'}")
    print(f"  TELEGRAM_API_ID    : {'✅ set (' + api_id_str + ')' if api_id_str else '❌ MISSING'}")
    print(f"  TELEGRAM_API_HASH  : {'✅ set (***' + api_hash[-4:] + ')' if api_hash else '❌ MISSING'}")

    missing = [n for n, v in [
        ("TELEGRAM_BOT_TOKEN", bot_token),
        ("TELEGRAM_API_ID",    api_id_str),
        ("TELEGRAM_API_HASH",  api_hash),
    ] if not v]
    if missing:
        print(f"\n❌ Aborting — missing vars: {', '.join(missing)}")
        sys.exit(1)

    try:
        api_id = int(api_id_str)
    except ValueError:
        print(f"\n❌ TELEGRAM_API_ID is not a valid integer: {api_id_str!r}")
        sys.exit(1)

    print("\n── Pyrogram connection test ──────────────────────────────────────")
    try:
        from pyrogram import Client
    except ImportError as exc:
        print(f"❌ pyrogram not installed: {exc}")
        sys.exit(1)

    # Use an in-memory session so no .session file is written
    print("  Connecting as bot (in-memory session)…")
    try:
        async with Client(
            ":memory:",
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
        ) as app:
            me = await app.get_me()
            print(f"  ✅ Connected — bot: @{me.username}  (id={me.id}, name={me.first_name})")
    except Exception as exc:
        print(f"  ❌ Connection failed: {exc}")
        sys.exit(1)

    print("\n✅ All checks passed — Pyrogram MTProto session works correctly.")


if __name__ == "__main__":
    asyncio.run(main())
