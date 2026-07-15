"""
One-time interactive authentication for the channel history importer.

Creates bot/channel_history_user.session — a Pyrogram user-account session
that allows messages.GetHistory (which bots cannot call via MTProto).

Run this ONCE from the Shell tab (not from the agent — it needs your input):

    cd /home/runner/workspace && python3 bot/channel_history/_auth.py

Telegram will send a code to the phone number you enter.
After successful login the session file is saved; you never need to run
this again unless the session expires or is revoked.

Required env vars (already set as Replit Secrets):
    TELEGRAM_API_ID
    TELEGRAM_API_HASH
"""
from __future__ import annotations

import asyncio
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BOT_ROOT  = os.path.dirname(_THIS_DIR)
for _p in (_BOT_ROOT, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)


async def main() -> None:
    api_id_str = os.environ.get("TELEGRAM_API_ID", "")
    api_hash   = os.environ.get("TELEGRAM_API_HASH", "")

    if not api_id_str or not api_hash:
        print("❌ TELEGRAM_API_ID and TELEGRAM_API_HASH must be set.")
        sys.exit(1)

    api_id = int(api_id_str)

    # Pyrogram 2.x MIN_CHANNEL_ID fix for large channel IDs
    import pyrogram.utils as _pyu
    _pyu.MIN_CHANNEL_ID = -1009999999999999

    from pyrogram import Client

    session_path = os.path.join(_BOT_ROOT, "channel_history_user")
    print(f"Session will be saved to: {session_path}.session")
    print("Telegram will send a login code to your phone.\n")

    async with Client(
        "channel_history_user",
        api_id=api_id,
        api_hash=api_hash,
        workdir=_BOT_ROOT,
    ) as app:
        me = await app.get_me()
        print(f"\n✅ Authenticated as: {me.first_name} (@{me.username}, id={me.id})")
        print(f"✅ Session saved to: {session_path}.session")
        print("\nYou can now run the channel history importer.")


if __name__ == "__main__":
    asyncio.run(main())
