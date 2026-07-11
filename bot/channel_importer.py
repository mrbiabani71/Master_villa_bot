"""
Channel importer — watches the configured Telegram channel for new villa posts,
parses them using the same Smart Import parser, and saves villas + photos to DB.

Uses ONLY Bot API updates (python-telegram-bot / long polling) — no Telethon,
no Pyrogram, no API_ID/API_HASH. The bot must be an admin of the channel to
receive channel_post / edited_channel_post updates.

Idempotency: every import goes through import_villa_from_channel(), which
upserts by telegram_message_id (the Bot API message_id of the post that
carries the caption/text). Re-processing the same post — e.g. after a bot
restart mid-album-buffer, or when the admin edits a channel post — updates
the existing villa instead of creating a duplicate.
"""

import asyncio
import logging

from telegram import Update, Bot, Message
from telegram.ext import ContextTypes, MessageHandler, filters

from config import ADMIN_ID, CHANNEL_ID
from smart_import.parser import parse_villa_text
from smart_import.importer import import_villa_from_channel

logger = logging.getLogger(__name__)


# ── Text extraction helper ─────────────────────────────────────────────────────

def _extract_text(post: Message) -> str:
    """
    Return the best available text from a channel post.

    Telegram stores text differently depending on the post type:
      • text-only post  → post.text
      • photo/video/doc with caption → post.caption
    We always try caption first (covers both), then fall back to text.
    """
    return (post.caption or post.text or "").strip()


# ── Media group buffer ─────────────────────────────────────────────────────────
# Keyed by media_group_id.  Collects caption + all photo file_ids + message ids
# until the group is complete (detected by a short quiet-period timeout).

_buffer: dict[str, dict] = {}
_TIMEOUT = 2.5  # seconds to wait after the last photo in the group arrives


async def _flush_group(group_id: str, bot: Bot) -> None:
    """Called after the timeout; processes the buffered media group."""
    await asyncio.sleep(_TIMEOUT)
    entry = _buffer.pop(group_id, None)
    if entry is None:
        return
    await _save_villa(
        bot,
        text=entry.get("caption", ""),
        photo_ids=entry.get("photo_ids", []),
        message_id=entry["message_id"],
        media_group_id=group_id,
    )


# ── Core save logic ────────────────────────────────────────────────────────────

async def _save_villa(
    bot: Bot,
    text: str,
    photo_ids: list[str],
    message_id: int,
    media_group_id: str | None,
) -> None:
    """
    Parse text using the Smart Import parser, attach Telegram provenance,
    upsert into DB (idempotent by message_id), and notify admin.
    """
    logger.debug(
        "CHANNEL_IMPORT | incoming text (%d chars) msg_id=%s group=%s:\n%s",
        len(text), message_id, media_group_id, text,
    )

    if not text:
        logger.warning("CHANNEL_IMPORT | empty text — ignoring update")
        return

    data = parse_villa_text(text)
    data.photos = list(photo_ids)
    data.telegram_message_id = message_id
    data.telegram_media_group_id = media_group_id
    data.original_caption = text

    logger.debug(
        "CHANNEL_IMPORT | parsed → code=%s city=%s price=%s photos=%d",
        data.villa_code, data.city, data.price, len(data.photos),
    )

    # All four fields must be present before we touch the database.
    # If any is missing the post is incomplete — ignore it silently.
    missing = [
        name
        for name, val in [
            ("city",          data.city),
            ("price",         data.price),
            ("land_size",     data.land_size),
            ("building_size", data.building_size),
        ]
        if val is None
    ]
    if missing:
        logger.info(
            "CHANNEL_IMPORT | IGNORED — missing required fields: %s",
            ", ".join(missing),
        )
        return

    result = import_villa_from_channel(data)

    if result.success:
        verb = "به‌روزرسانی" if result.mode == "update" else "ذخیره"
        price_b = (data.price or 0) / 1_000_000_000
        await bot.send_message(
            ADMIN_ID,
            f"✅ ویلا از کانال {verb} شد\n\n"
            f"🏷 کد: <b>{result.villa_code}</b>\n"
            f"📍 شهر: {data.city or '—'}  |  {data.area_type or '—'}\n"
            f"💰 قیمت: {price_b:.2f} میلیارد\n"
            f"🖼 تعداد عکس: {len(photo_ids)}",
            parse_mode="HTML",
        )
        logger.info(
            "CHANNEL_IMPORT | %s villa %s (id=%s, msg_id=%s, photos=%d)",
            result.mode, result.villa_code, result.villa_id, message_id, len(photo_ids),
        )
    else:
        await bot.send_message(
            ADMIN_ID,
            f"❌ خطا در ذخیره ویلا از کانال:\n{result.error}",
        )
        logger.error("CHANNEL_IMPORT | save failed: %s", result.error)


# ── PTB handler ────────────────────────────────────────────────────────────────

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Cover both new posts and edits to an existing post — both are safe to
    # re-process because the upsert keys off telegram_message_id.
    post = update.channel_post or update.edited_channel_post
    if post is None:
        return

    # If CHANNEL_ID is configured, ignore posts from other channels
    if CHANNEL_ID and post.chat.id != CHANNEL_ID:
        return

    # ── Case 1: plain text post (no photos) ───────────────────────────────────
    if not post.photo:
        text = _extract_text(post)
        if text:
            await _save_villa(
                context.bot, text, [],
                message_id=post.message_id, media_group_id=None,
            )
        return

    # ── Case 2: photo(s) ──────────────────────────────────────────────────────
    best = post.photo[-1].file_id  # highest-resolution variant

    # Single photo (not part of a media group)
    if not post.media_group_id:
        text = _extract_text(post)
        await _save_villa(
            context.bot, text, [best],
            message_id=post.message_id, media_group_id=None,
        )
        return

    # Part of a media group — buffer until all photos have arrived.
    # The canonical telegram_message_id for the whole album is the lowest
    # message_id seen in the group (albums arrive in ascending order), so it
    # stays stable across retries/edits of the same album.
    gid = post.media_group_id
    text = _extract_text(post)  # non-empty only on the message that carries caption

    if gid not in _buffer:
        _buffer[gid] = {
            "caption": text,
            "photo_ids": [],
            "task": None,
            "message_id": post.message_id,
        }
    else:
        if text:
            # Update caption if this message carries one (whichever arrives last
            # wins, which is fine because only one message per group has a caption)
            _buffer[gid]["caption"] = text
        _buffer[gid]["message_id"] = min(_buffer[gid]["message_id"], post.message_id)

    _buffer[gid]["photo_ids"].append(best)

    # (Re)schedule the flush — keeps sliding until photos stop arriving
    old_task: asyncio.Task | None = _buffer[gid].get("task")
    if old_task and not old_task.done():
        old_task.cancel()
    _buffer[gid]["task"] = asyncio.create_task(
        _flush_group(gid, context.bot)
    )


def channel_import_handler() -> MessageHandler:
    """Return the MessageHandler that should be added to the Application."""
    return MessageHandler(
        filters.UpdateType.CHANNEL_POSTS | filters.UpdateType.EDITED_CHANNEL_POST,
        handle_channel_post,
    )
