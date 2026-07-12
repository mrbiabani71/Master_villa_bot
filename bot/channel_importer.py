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
Style A (existing): media group where one message carries a caption.
Style B (new):      media group with NO caption, followed within 60 seconds
                    by a plain text-only message from the same channel.  The
                    text message is treated as the description for that album.
"""

import asyncio
import logging
import time

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


# ── Media group buffer (Style A) ───────────────────────────────────────────────
# Keyed by media_group_id.  Collects caption + all photo file_ids + message ids
# until the group is complete (detected by a short quiet-period timeout).

_buffer: dict[str, dict] = {}
_TIMEOUT = 2.5  # seconds to wait after the last photo in the group arrives


# ── Pending-caption buffer (Style B) ──────────────────────────────────────────
# Keyed by chat_id.  Stores caption-less media groups waiting for a follow-up
# text message.  Entry expires after _CAPTION_WAIT seconds.

_pending_caption: dict[int, dict] = {}
_CAPTION_WAIT = 60  # seconds to wait for a follow-up text message


async def _flush_group(group_id: str, bot: Bot, chat_id: int) -> None:
    """Called after the timeout; processes the buffered media group."""
    await asyncio.sleep(_TIMEOUT)
    entry = _buffer.pop(group_id, None)
    if entry is None:
        return

    caption = entry.get("caption", "")

    if caption:
        # Style A: caption present — import immediately as before.
        await _save_villa(
            bot,
            text=caption,
            photo_ids=entry.get("photo_ids", []),
            message_id=entry["message_id"],
            media_group_id=group_id,
        )
    else:
        # Style B: no caption — park the album and wait up to 60 s for a
        # follow-up text message from the same channel.
        _pending_caption[chat_id] = {
            "group_id":  group_id,
            "photo_ids": entry.get("photo_ids", []),
            "message_id": entry["message_id"],
            "expires_at": time.monotonic() + _CAPTION_WAIT,
        }
        logger.debug(
            "CHANNEL_IMPORT | media group %s has no caption — waiting up to %ds "
            "for a follow-up text message (chat_id=%s, msg_id=%s)",
            group_id, _CAPTION_WAIT, chat_id, entry["message_id"],
        )
        # Schedule expiry cleanup so stale entries don't linger forever.
        asyncio.create_task(_expire_pending(chat_id, bot, entry["message_id"]))


async def _expire_pending(chat_id: int, bot: Bot, message_id: int) -> None:
    """After the wait window, discard any unfulfilled pending-caption entry and notify admin."""
    await asyncio.sleep(_CAPTION_WAIT + 1)
    entry = _pending_caption.pop(chat_id, None)
    if entry is None:
        # Already consumed by a follow-up text — nothing to do.
        return

    reason = "آلبوم بدون کپشن — پیام متنی دنباله‌دار در ۶۰ ثانیه دریافت نشد"
    logger.warning(
        "CHANNEL_IMPORT | IGNORED (Style-B timeout) msg_id=%s group=%s — %s",
        message_id, entry.get("group_id"), reason,
    )
    await _notify_failure(bot, message_id, reason)


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
        "CHANNEL_IMPORT | incoming text (%d chars) msg_id=%s group=%s:\n%s",
        len(text), message_id, media_group_id, text,
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

    logger.debug(
        "CHANNEL_IMPORT | parsed → code=%s city=%s price=%s photos=%d",
        data.villa_code, data.city, data.price, len(data.photos),
    )

    # ── Required-field validation ──────────────────────────────────────────────
    # Only city and price are strictly required to save a post — land_size and
    # building_size are optional and stored as NULL when missing (warned below)
    # rather than causing the whole post to be discarded.
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

    # If CHANNEL_ID is configured, ignore posts from other channels
    if CHANNEL_ID and post.chat.id != CHANNEL_ID:
        return

    chat_id = post.chat.id

    # ── Case 1: plain text post (no photos) ───────────────────────────────────
    if not post.photo:
        text = _extract_text(post)
        if not text:
            return

        # Style B: check whether a caption-less album is waiting for this text.
        pending = _pending_caption.get(chat_id)
        if pending and time.monotonic() < pending["expires_at"]:
            # Consume the pending entry and import as a captioned album.
            del _pending_caption[chat_id]
            logger.debug(
                "CHANNEL_IMPORT | Style-B match — using text msg_id=%s as caption "
                "for album msg_id=%s group=%s",
                post.message_id, pending["message_id"], pending["group_id"],
            )
            await _save_villa(
                context.bot,
                text=text,
                photo_ids=pending["photo_ids"],
                message_id=pending["message_id"],
                media_group_id=pending["group_id"],
            )
        else:
            # No pending album (or it expired) — treat as a standalone text post.
            if pending:
                # Expired entry — clean it up silently (the expiry task will
                # have already sent the notification once it wakes up, so we
                # just remove the stale dict entry here).
                del _pending_caption[chat_id]
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
            "caption":    text,
            "photo_ids":  [],
            "task":       None,
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
        _flush_group(gid, context.bot, chat_id)
    )


def channel_import_handler() -> MessageHandler:
    """Return the MessageHandler that should be added to the Application."""
    return MessageHandler(
        filters.UpdateType.CHANNEL_POSTS | filters.UpdateType.EDITED_CHANNEL_POST,
        handle_channel_post,
    )
