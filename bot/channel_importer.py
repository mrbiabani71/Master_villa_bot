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

Posting styles supported
------------------------
Style A (caption-attached):
    A media group (or single photo) where one message already carries a
    caption.  Imported immediately when the group buffer flushes.

Style B (photos-then-text):
    Our standard channel workflow.  All villa photos are sent first —
    Telegram may split a large album into multiple consecutive media groups.
    A plain text message follows as the villa description / caption.
    The text message is the boundary that finalises the villa.

    All consecutive caption-less groups from the same channel are accumulated
    in _photo_accumulator (keyed by chat_id).  When the text message arrives
    ALL accumulated photos are attached to one villa.  The photo count is
    unlimited.  After the text message is consumed the accumulator resets and
    the next batch starts fresh.

    A 10-minute safety timeout discards a stale accumulator and notifies the
    admin if no caption ever arrives (e.g. the operator forgot to send the text).
"""

import asyncio
import logging
import time

from telegram import Update, Bot, Message
from telegram.ext import ContextTypes, MessageHandler, filters

from config import ADMIN_ID, CHANNEL_ID
from smart_import.parser import parse_villa_text
from smart_import.importer import import_villa_from_channel
from notifications import dispatch_new_villa_notification

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


# ── Per-group buffer (used for both Style A and B) ────────────────────────────
# Keyed by media_group_id.  Collects caption + all photo file_ids + message ids
# until the group is complete (detected by a short quiet-period timeout).

_buffer: dict[str, dict] = {}
_TIMEOUT = 2.5  # seconds to wait after the last photo in the group arrives


# ── Cross-group photo accumulator (Style B) ───────────────────────────────────
# Keyed by chat_id.  Stacks photo file_ids from consecutive caption-less media
# groups (or single caption-less photos) until a plain text message arrives.
#
# Structure of each entry:
#   {
#     "photo_ids":       list[str],   # all accumulated file_ids so far
#     "first_message_id": int,        # message_id of the first contributing post
#     "first_group_id":  str | None,  # media_group_id of the first contributing group
#     "group_count":     int,         # how many groups have been merged
#     "stale_task":      asyncio.Task # safety-timeout cleanup task
#   }

_photo_accumulator: dict[int, dict] = {}
_STALE_TIMEOUT = 600  # 10 minutes — safety net only, NOT the primary boundary


async def _flush_group(group_id: str, bot: Bot, chat_id: int) -> None:
    """Called after the quiet-period timeout; processes the buffered media group."""
    await asyncio.sleep(_TIMEOUT)
    entry = _buffer.pop(group_id, None)
    if entry is None:
        return

    caption   = entry.get("caption", "")
    photo_ids = entry.get("photo_ids", [])
    message_id = entry["message_id"]

    if caption:
        # Style A: caption present on the album itself → import immediately.
        logger.debug(
            "CHANNEL_IMPORT | Style-A flush: group=%s msg_id=%s photos=%d",
            group_id, message_id, len(photo_ids),
        )
        await _save_villa(
            bot,
            text=caption,
            photo_ids=photo_ids,
            message_id=message_id,
            media_group_id=group_id,
        )
    else:
        # Style B: no caption → accumulate photos and wait for the text message.
        _accumulate(chat_id, photo_ids, message_id, group_id, bot)


def _accumulate(
    chat_id: int,
    photo_ids: list[str],
    message_id: int,
    group_id: str | None,
    bot: Bot,
) -> None:
    """
    Add photo_ids from a caption-less group (or single photo) to the running
    accumulator for this channel.  Creates the entry on first call.
    """
    if chat_id not in _photo_accumulator:
        # First caption-less group for this channel — create a new accumulator.
        stale_task = asyncio.create_task(
            _stale_cleanup(chat_id, message_id, bot)
        )
        _photo_accumulator[chat_id] = {
            "photo_ids":        list(photo_ids),
            "first_message_id": message_id,
            "first_group_id":   group_id,
            "group_count":      1,
            "stale_task":       stale_task,
        }
        logger.debug(
            "CHANNEL_IMPORT | Style-B accumulator started: chat_id=%s "
            "first_msg_id=%s first_group=%s photos_so_far=%d",
            chat_id, message_id, group_id, len(photo_ids),
        )
    else:
        # Subsequent group — append photos to the existing accumulator.
        acc = _photo_accumulator[chat_id]
        acc["photo_ids"].extend(photo_ids)
        acc["group_count"] += 1
        logger.debug(
            "CHANNEL_IMPORT | Style-B accumulator updated: chat_id=%s "
            "group=%s new_photos=%d total_photos=%d groups_merged=%d",
            chat_id, group_id, len(photo_ids),
            len(acc["photo_ids"]), acc["group_count"],
        )


async def _stale_cleanup(chat_id: int, first_message_id: int, bot: Bot) -> None:
    """
    Safety net: if no caption arrives within _STALE_TIMEOUT seconds, discard
    the accumulator and notify the admin.  This is NOT the normal import path —
    the caption message is the real boundary.
    """
    await asyncio.sleep(_STALE_TIMEOUT)
    acc = _photo_accumulator.pop(chat_id, None)
    if acc is None:
        # Already consumed by a caption message — nothing to do.
        return

    reason = (
        f"آلبوم‌های بدون کپشن (Style-B) — {acc['group_count']} گروه / "
        f"{len(acc['photo_ids'])} عکس — پس از ۱۰ دقیقه هنوز متن دریافت نشد"
    )
    logger.warning(
        "CHANNEL_IMPORT | STALE accumulator discarded: chat_id=%s "
        "first_msg_id=%s groups=%d photos=%d",
        chat_id, first_message_id, acc["group_count"], len(acc["photo_ids"]),
    )
    await _notify_failure(bot, first_message_id, reason)


# ── Admin notification helpers ─────────────────────────────────────────────────

async def _notify_failure(bot: Bot, message_id: int, reason: str) -> None:
    """Send admin a structured failure notification and write it to the log."""
    logger.error(
        "CHANNEL_IMPORT | FAILED msg_id=%s — %s",
        message_id, reason,
    )
    try:
        await bot.send_message(
            ADMIN_ID,
            f"❌ <b>خطا در ایمپورت ویلا</b>\n\n"
            f"🆔 شناسه پیام: <code>{message_id}</code>\n"
            f"📋 دلیل: {reason}",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("CHANNEL_IMPORT | could not send failure notification: %s", exc)


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
        "CHANNEL_IMPORT | incoming text (%d chars) msg_id=%s group=%s photos=%d:\n%s",
        len(text), message_id, media_group_id, len(photo_ids), text,
    )

    if not text:
        reason = "متن خالی — هیچ کپشن یا متنی در پیام یافت نشد"
        logger.warning("CHANNEL_IMPORT | IGNORED msg_id=%s — %s", message_id, reason)
        await _notify_failure(bot, message_id, reason)
        return

    data = parse_villa_text(text)
    data.photos = list(photo_ids)
    data.telegram_message_id = message_id
    data.telegram_media_group_id = media_group_id
    data.original_caption = text

    logger.info(
        "CHANNEL_IMPORT | pre-import summary: msg_id=%s photos=%d "
        "parsed→ code=%s city=%s price=%s",
        message_id, len(photo_ids), data.villa_code, data.city, data.price,
    )

    # ── Required-field validation ──────────────────────────────────────────────
    missing_required = [
        name
        for name, val in [
            ("city",  data.city),
            ("price", data.price),
        ]
        if val is None
    ]
    if missing_required:
        field_labels = {
            "city":  "شهر (city)",
            "price": "قیمت (price)",
        }
        missing_fa = " و ".join(field_labels[f] for f in missing_required)
        reason = f"فیلدهای ضروری یافت نشد: {missing_fa}"
        logger.info(
            "CHANNEL_IMPORT | IGNORED msg_id=%s — %s | text=%r",
            message_id, reason, text[:200],
        )
        await _notify_failure(bot, message_id, reason)
        return

    # ── Optional-field warnings ────────────────────────────────────────────────
    missing_optional = [
        name
        for name, val in [
            ("land_size",     data.land_size),
            ("building_size", data.building_size),
        ]
        if val is None
    ]
    if missing_optional:
        logger.warning(
            "CHANNEL_IMPORT | msg_id=%s — saving villa with missing optional fields "
            "(will be NULL): %s",
            message_id, ", ".join(missing_optional),
        )

    # ── Persist ────────────────────────────────────────────────────────────────
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
        if result.mode == "create":
            asyncio.create_task(dispatch_new_villa_notification(bot, result.villa_id))
    else:
        reason = result.error or "خطای ناشناخته در ذخیره‌سازی"
        logger.error(
            "CHANNEL_IMPORT | FAILED msg_id=%s — API error: %s",
            message_id, reason,
        )
        await bot.send_message(
            ADMIN_ID,
            f"❌ <b>خطا در ذخیره ویلا از کانال</b>\n\n"
            f"🆔 شناسه پیام: <code>{message_id}</code>\n"
            f"📋 دلیل: {reason}",
            parse_mode="HTML",
        )


# ── PTB handler ────────────────────────────────────────────────────────────────

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Cover both new posts and edits to an existing post — both are safe to
    # re-process because the upsert keys off telegram_message_id.
    post = update.channel_post or update.edited_channel_post
    if post is None:
        return

    logger.debug(
        "CHANNEL_IMPORT | received update chat_id=%s message_id=%s",
        post.chat.id, post.message_id,
    )

    # If CHANNEL_ID is configured, ignore posts from other channels.
    if CHANNEL_ID and post.chat.id != CHANNEL_ID:
        return

    chat_id = post.chat.id

    # ── Case 1: plain text post (no photos) ───────────────────────────────────
    if not post.photo:
        text = _extract_text(post)
        if not text:
            return

        acc = _photo_accumulator.pop(chat_id, None)

        if acc is not None:
            # Cancel the stale-cleanup task — caption arrived in time.
            stale_task: asyncio.Task = acc.get("stale_task")
            if stale_task and not stale_task.done():
                stale_task.cancel()

            logger.info(
                "CHANNEL_IMPORT | Style-B caption received: chat_id=%s "
                "msg_id=%s — attaching %d photos from %d group(s) → importing villa",
                chat_id, post.message_id,
                len(acc["photo_ids"]), acc["group_count"],
            )
            # Import using the first photo message's id as the villa's provenance key.
            await _save_villa(
                context.bot,
                text=text,
                photo_ids=acc["photo_ids"],
                message_id=acc["first_message_id"],
                media_group_id=acc["first_group_id"],
            )
        else:
            # No accumulated photos — standalone text-only villa post.
            await _save_villa(
                context.bot, text, [],
                message_id=post.message_id, media_group_id=None,
            )
        return

    # ── Case 2: photo(s) ──────────────────────────────────────────────────────
    best = post.photo[-1].file_id  # highest-resolution variant

    # Single photo (not part of a media group).
    if not post.media_group_id:
        text = _extract_text(post)
        if text:
            # Has its own caption → Style A, import immediately.
            logger.debug(
                "CHANNEL_IMPORT | Style-A single photo: msg_id=%s", post.message_id,
            )
            await _save_villa(
                context.bot, text, [best],
                message_id=post.message_id, media_group_id=None,
            )
        else:
            # No caption → treat as the start (or continuation) of a Style-B batch.
            _accumulate(chat_id, [best], post.message_id, None, context.bot)
        return

    # Part of a media group — buffer until all photos have arrived.
    # The canonical telegram_message_id for the whole album is the lowest
    # message_id seen in the group (albums arrive in ascending order), so it
    # stays stable across retries/edits of the same album.
    gid  = post.media_group_id
    text = _extract_text(post)  # non-empty only on the message that carries caption

    if gid not in _buffer:
        _buffer[gid] = {
            "caption":    text,
            "photo_ids":  [],
            "task":       None,
            "message_id": post.message_id,
        }
    else:
        if text:
            # Update caption if this message carries one (whichever arrives last
            # wins, which is fine because only one message per group has a caption).
            _buffer[gid]["caption"] = text
        _buffer[gid]["message_id"] = min(_buffer[gid]["message_id"], post.message_id)

    _buffer[gid]["photo_ids"].append(best)

    # (Re)schedule the flush — keeps sliding until photos stop arriving.
    old_task: asyncio.Task | None = _buffer[gid].get("task")
    if old_task and not old_task.done():
        old_task.cancel()
    _buffer[gid]["task"] = asyncio.create_task(
        _flush_group(gid, context.bot, chat_id)
    )


def channel_import_handler() -> MessageHandler:
    """Return the MessageHandler that should be added to the Application."""
    return MessageHandler(
        filters.UpdateType.CHANNEL_POSTS | filters.UpdateType.EDITED_CHANNEL_POST,
        handle_channel_post,
    )
