"""
Channel history collector — fetches all messages from a Telegram channel via
Pyrogram (MTProto) and groups them into VillaGroups ready for the importer.

Grouping rules
--------------
1. Messages that share a media_group_id form an album.
2. If an album has a caption → use it as the villa text.
3. If an album has NO caption and the immediately following message is a plain
   text post (no photo / document / video) → use that next message's text as
   the villa description and consume it (skip it as a standalone entry).
4. Single-photo messages (no media_group_id) follow the same caption-or-lookahead
   rule as albums.
5. Standalone plain-text messages (no photos at all) are included as text-only
   groups for the parser to process.
6. All other message types (stickers, voice notes, polls, etc.) are skipped.

The function returns groups in CHRONOLOGICAL order (oldest first).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VillaGroup:
    """
    A single importable unit — one villa's worth of data extracted from one or
    more consecutive Telegram messages.
    """
    text: str                          # best available text (caption / lookahead / body)
    photo_file_ids: list[str]          # Telegram file_ids for each photo (highest res)
    telegram_message_id: int           # primary message ID (lowest in the group)
    telegram_media_group_id: str | None   # album group ID, or None for single posts
    original_caption: str              # raw album caption (empty if none in the album)
    message_ids: list[int]             # all message IDs consumed by this group
    is_text_only: bool = False         # True when no photos at all


# ── Internal helpers ──────────────────────────────────────────────────────────

def _best_photo_file_id(msg) -> str | None:
    """Return the highest-resolution photo file_id from a Pyrogram Message, or None."""
    if msg.photo:
        return msg.photo.file_id
    return None


def _is_plain_text(msg) -> bool:
    """True when the message is text-only (no attached media of any kind)."""
    return bool(msg.text) and not any([
        msg.photo, msg.document, msg.video, msg.audio,
        msg.voice, msg.video_note, msg.sticker, msg.animation,
    ])


def _group_messages(messages: list) -> list[VillaGroup]:
    """
    Process a chronologically-sorted message list into VillaGroups.

    The algorithm uses a forward index pointer so we can consume
    lookahead plain-text messages without double-processing them.
    """
    groups: list[VillaGroup] = []
    i = 0
    n = len(messages)

    while i < n:
        msg = messages[i]

        # ── Album (media group) ────────────────────────────────────────────────
        if msg.media_group_id:
            gid = msg.media_group_id

            # Collect all consecutive messages belonging to this album
            album: list = [msg]
            j = i + 1
            while j < n and messages[j].media_group_id == gid:
                album.append(messages[j])
                j += 1

            # Caption: take the first non-empty caption found in the album
            caption = ""
            for am in album:
                if am.caption:
                    caption = am.caption
                    break

            # Photo file_ids (one per album message that has a photo)
            photo_ids = [
                fid for am in album
                if (fid := _best_photo_file_id(am)) is not None
            ]

            # Lookahead: if no caption, check the next message for plain text
            text = caption
            consumed_lookahead = 0
            if not text and j < n and _is_plain_text(messages[j]):
                text = messages[j].text
                consumed_lookahead = 1
                logger.debug(
                    "Album msg_id=%d: no caption — using lookahead text from msg_id=%d",
                    album[0].id, messages[j].id,
                )

            if text or photo_ids:
                all_ids = [am.id for am in album]
                if consumed_lookahead and j < n:
                    all_ids.append(messages[j].id)
                groups.append(VillaGroup(
                    text=text.strip(),
                    photo_file_ids=photo_ids,
                    telegram_message_id=album[0].id,
                    telegram_media_group_id=gid,
                    original_caption=caption.strip(),
                    message_ids=all_ids,
                ))

            i = j + consumed_lookahead

        # ── Single photo (not part of a media group) ───────────────────────────
        elif msg.photo:
            caption = msg.caption or ""

            # Lookahead for plain-text description
            text = caption
            consumed_lookahead = 0
            if not text and i + 1 < n and _is_plain_text(messages[i + 1]):
                text = messages[i + 1].text
                consumed_lookahead = 1
                logger.debug(
                    "Single photo msg_id=%d: no caption — using lookahead text from msg_id=%d",
                    msg.id, messages[i + 1].id,
                )

            fid = _best_photo_file_id(msg)
            all_ids = [msg.id]
            if consumed_lookahead and i + 1 < n:
                all_ids.append(messages[i + 1].id)
            groups.append(VillaGroup(
                text=text.strip(),
                photo_file_ids=[fid] if fid else [],
                telegram_message_id=msg.id,
                telegram_media_group_id=None,
                original_caption=caption.strip(),
                message_ids=all_ids,
            ))
            i += 1 + consumed_lookahead

        # ── Standalone plain-text message ─────────────────────────────────────
        elif msg.text:
            groups.append(VillaGroup(
                text=msg.text.strip(),
                photo_file_ids=[],
                telegram_message_id=msg.id,
                telegram_media_group_id=None,
                original_caption="",
                message_ids=[msg.id],
                is_text_only=True,
            ))
            i += 1

        # ── Skip non-importable message types ─────────────────────────────────
        else:
            i += 1

    return groups


# ── Public entry point ────────────────────────────────────────────────────────

async def collect_channel_history(
    bot_token: str,
    api_id: int,
    api_hash: str,
    channel_id: int,
    *,
    workdir: str | None = None,
) -> list[VillaGroup]:
    """
    Fetch the complete message history of *channel_id* and return a list of
    VillaGroups in chronological order.

    Parameters
    ----------
    bot_token : str
        Telegram bot token.  The bot must be an admin of the target channel.
    api_id : int
        API ID from my.telegram.org.
    api_hash : str
        API hash from my.telegram.org.
    channel_id : int
        Numeric channel ID (e.g. -1001234567890).
    workdir : str | None
        Directory where Pyrogram stores the session file.
        Defaults to the ``bot/`` directory of this project.
    """
    try:
        from pyrogram import Client
    except ImportError as exc:
        raise RuntimeError(
            "pyrogram is required for channel history import.\n"
            "Install it with:  uv add pyrogram\n"
            f"Original error: {exc}"
        ) from exc

    if workdir is None:
        # Store the session next to this file (inside bot/)
        workdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    session_name = "channel_history_bot"
    logger.info(
        "collect_channel_history: connecting (channel=%s, session=%s/%s.session)",
        channel_id, workdir, session_name,
    )

    all_messages: list = []

    async with Client(
        session_name,
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token,
        workdir=workdir,
    ) as app:
        async for message in app.get_chat_history(channel_id):
            all_messages.append(message)

    logger.info(
        "collect_channel_history: fetched %d raw messages — grouping…",
        len(all_messages),
    )

    # get_chat_history returns newest-first; reverse to chronological order.
    all_messages.sort(key=lambda m: m.id)

    groups = _group_messages(all_messages)

    logger.info(
        "collect_channel_history: produced %d villa groups from %d messages",
        len(groups), len(all_messages),
    )
    return groups
