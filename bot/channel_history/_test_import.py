"""
Controlled import test — fetches enough raw messages to form 20 villa groups,
imports them, then optionally re-runs to verify idempotency (update not duplicate).

Does NOT modify any importer logic.  Safe to re-run (idempotent upserts).

Usage (from the project root):
    python3 bot/channel_history/_test_import.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

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

RAW_FETCH_LIMIT = 300   # raw messages to pull — enough to form 20+ groups
GROUP_CAP       = 20    # import the most recent N groups


def _group_type(g) -> str:
    if g.telegram_media_group_id:
        return f"album({len(g.photo_file_ids)}p)"
    if len(g.photo_file_ids) == 1:
        return "single(1p)"
    if len(g.photo_file_ids) == 2:
        return "two(2p)"
    if g.photo_file_ids:
        return f"multi({len(g.photo_file_ids)}p)"
    return "text-only"


async def run_import(groups, pass_label: str) -> list:
    from channel_history.importer import import_villa_groups
    print(f"\n── {pass_label} ─────────────────────────────────────────────────")
    results = await import_villa_groups(groups)
    return results


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
    api_port  = os.environ.get("API_SERVER_PORT", "8080")
    health_url = f"http://localhost:{api_port}/api/healthz"
    try:
        with httpx.Client(timeout=5) as c:
            c.get(health_url).raise_for_status()
        print(f"✅ API server reachable at {health_url}")
    except Exception as exc:
        print(f"❌ API server not reachable: {exc}")
        sys.exit(1)

    # ── 3. Patch Pyrogram large-channel-ID limit, import collector helpers ────
    import pyrogram.utils as _pyu
    _pyu.MIN_CHANNEL_ID = -1009999999999999

    from pyrogram import Client
    from channel_history.collector import _group_messages

    session_file = os.path.join(_BOT_ROOT, "channel_history_user.session")
    if not os.path.exists(session_file):
        print(f"❌ User session not found: {session_file}")
        print("   Run:  python3 bot/channel_history/_auth.py")
        sys.exit(1)

    # ── 4. Fetch raw messages via Pyrogram user session ───────────────────────
    print(f"\nFetching latest {RAW_FETCH_LIMIT} raw messages from channel {channel_id}…")
    raw_messages: list = []
    async with Client("channel_history_user", api_id=api_id, api_hash=api_hash,
                      workdir=_BOT_ROOT) as app:
        async for msg in app.get_chat_history(channel_id, limit=RAW_FETCH_LIMIT):
            raw_messages.append(msg)

    raw_messages.sort(key=lambda m: m.id)
    print(f"  Raw messages fetched : {len(raw_messages)}")

    # ── 5. Group → take latest GROUP_CAP ─────────────────────────────────────
    all_groups = _group_messages(raw_messages)
    groups     = all_groups[-GROUP_CAP:]
    print(f"  Villa groups formed  : {len(all_groups)}  (importing last {len(groups)})")

    if not groups:
        print("No importable groups — nothing to import.")
        return

    # ── 6. Group preview ──────────────────────────────────────────────────────
    print("\n── Group preview ─────────────────────────────────────────────────")
    for i, g in enumerate(groups):
        cap = (g.text[:55] + "…") if len(g.text) > 55 else g.text
        cap = cap.replace("\n", " ")
        print(
            f"  [{i+1:2d}] msg_id={g.telegram_message_id:<6}  "
            f"type={_group_type(g):<14}  "
            f"has_text={bool(g.text)!s:<5}  "
            f"{cap!r}"
        )

    # ── 7. Pass 1 — fresh import ──────────────────────────────────────────────
    results1 = await run_import(groups, "Pass 1 — fresh import")
    _print_summary("Pass 1", groups, results1, len(raw_messages))

    # ── 8. Pass 2 — re-import same posts (idempotency check) ─────────────────
    results2 = await run_import(groups, "Pass 2 — re-import (idempotency check)")
    _print_summary("Pass 2", groups, results2, len(raw_messages))

    # ── 9. Idempotency verdict ────────────────────────────────────────────────
    print("\n── Idempotency verdict ───────────────────────────────────────────")
    pass2_creates = [r for r in results2 if r.success and r.mode == "create"]
    pass2_updates = [r for r in results2 if r.success and r.mode == "update"]
    pass2_failed  = [r for r in results2 if not r.success]
    if pass2_creates:
        print(f"  ❌ FAIL — {len(pass2_creates)} duplicate(s) created on re-import")
        for r in pass2_creates:
            print(f"       code={r.villa_code}")
    elif pass2_failed:
        print(f"  ⚠️  {len(pass2_failed)} item(s) failed on re-import (see Pass 2 failures)")
    else:
        print(f"  ✅ PASS — all {len(pass2_updates)} groups updated in place, 0 duplicates")


def _print_summary(label: str, groups, results, raw_count: int) -> None:
    created  = [r for r in results if r.success and r.mode == "create"]
    updated  = [r for r in results if r.success and r.mode == "update"]
    failed   = [r for r in results if not r.success]
    skipped  = len(groups) - len(results)

    # Build a msg_id → result map for failure reporting
    code_to_group = {g.telegram_message_id: g for g in groups}
    result_codes  = [r.villa_code for r in results]

    # Album / photo stats
    groups_with_text   = [g for g in groups if g.text]
    single_photo       = [g for g in groups if len(g.photo_file_ids) == 1 and not g.telegram_media_group_id]
    two_photo          = [g for g in groups if len(g.photo_file_ids) == 2 and not g.telegram_media_group_id]
    albums             = [g for g in groups if g.telegram_media_group_id]
    total_photos       = sum(len(g.photo_file_ids) for g in groups)

    print(f"\n{'═'*62}")
    print(f"  {label} Summary")
    print(f"{'═'*62}")
    print(f"  Raw messages checked     : {raw_count}")
    print(f"  Villa groups imported    : {len(groups)}")
    print(f"  ✅ New villas created    : {len(created)}")
    for r in created:
        print(f"       code={r.villa_code}  id={r.villa_id}")
    print(f"  🔄 Updated villas        : {len(updated)}")
    for r in updated:
        print(f"       code={r.villa_code}  id={r.villa_id}")
    print(f"  ⏭  Skipped (no text)     : {skipped}")
    print(f"  ❌ Failed                : {len(failed)}")
    for r in failed:
        # find corresponding group for msg_id
        msg_id = next(
            (g.telegram_message_id for g in groups if
             (g.telegram_message_id and r.villa_code and True) or True),
            "?"
        )
        # match by iterating groups in order
        print(f"       error={r.error}")
    print(f"\n  Photo / caption coverage:")
    print(f"    Albums (multi-photo)   : {len(albums)}/{len(groups)}  "
          f"(total photos in albums: {sum(len(g.photo_file_ids) for g in albums)})")
    print(f"    Single-photo posts     : {len(single_photo)}/{len(groups)}")
    print(f"    Two-photo posts        : {len(two_photo)}/{len(groups)}")
    print(f"    Groups with caption    : {len(groups_with_text)}/{len(groups)}")
    print(f"    Total photos stored    : {total_photos}")
    print(f"{'═'*62}")


if __name__ == "__main__":
    asyncio.run(main())
