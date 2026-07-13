"""
Admin panel: 📥 ایمپورت از کانال

Shows a confirmation step with channel details, then runs the full
channel-history import pipeline (Pyrogram collect → smart-import upsert)
and reports a structured summary.

Required env vars (beyond TELEGRAM_BOT_TOKEN):
    TELEGRAM_API_ID   — integer from https://my.telegram.org
    TELEGRAM_API_HASH — string  from https://my.telegram.org
    CHANNEL_ID        — numeric channel ID, e.g. -1001234567890
"""
from __future__ import annotations

import asyncio
import logging
import os

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import ADMIN_ID
from keyboards import admin_panel_keyboard

logger = logging.getLogger(__name__)

_REQUIRED_VARS = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "CHANNEL_ID"]


def _check_env() -> tuple[bool, list[str]]:
    """Return (all_present, list_of_missing_var_names)."""
    missing = [v for v in _REQUIRED_VARS if not os.environ.get(v)]
    return (len(missing) == 0, missing)


# ── Keyboard button handler ────────────────────────────────────────────────────

async def handle_import_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 📥 ایمپورت از کانال keyboard button — shows confirmation."""
    if update.effective_user.id != ADMIN_ID:
        return

    ok, missing = _check_env()
    if not ok:
        missing_str = "\n".join(f"• `{v}`" for v in missing)
        await update.message.reply_text(
            "⚠️ *ایمپورت کانال غیرفعال است*\n\n"
            "متغیرهای محیطی زیر تنظیم نشده‌اند:\n\n"
            f"{missing_str}\n\n"
            "برای فعال‌سازی:\n"
            "۱. به https://my.telegram.org بروید\n"
            "۲. `API ID` و `API Hash` را دریافت کنید\n"
            "۳. شناسه عددی کانال را در `CHANNEL_ID` وارد کنید\n"
            "۴. هر سه مقدار را در Replit Secrets ذخیره کنید",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard,
        )
        return

    channel_id = os.environ.get("CHANNEL_ID", "—")
    await update.message.reply_text(
        "📥 *تأیید ایمپورت از کانال*\n\n"
        f"🔗 کانال: `{channel_id}`\n\n"
        "این عملیات:\n"
        "• تمام پیام‌های کانال را بررسی می‌کند\n"
        "• ویلاهای جدید ایجاد می‌شوند\n"
        "• ویلاهای موجود (بر اساس شناسه پیام) به‌روز می‌شوند\n"
        "• هیچ ویلای تکراری ایجاد *نخواهد شد*\n\n"
        "⚠️ این عملیات ممکن است چند دقیقه طول بکشد.\n\n"
        "آیا مطمئن هستید؟",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، شروع ایمپورت", callback_data="ch_import_confirm"),
                InlineKeyboardButton("❌ انصراف",             callback_data="ch_import_cancel"),
            ],
        ]),
    )


# ── Inline: cancel ─────────────────────────────────────────────────────────────

async def cb_import_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ ایمپورت لغو شد.", reply_markup=None)


# ── Inline: confirm → run import ──────────────────────────────────────────────

async def cb_import_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run the full collect → upsert pipeline and report a summary."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    ok, missing = _check_env()
    if not ok:
        await query.edit_message_text(
            f"⚠️ متغیرهای محیطی لازم تنظیم نشده‌اند: {', '.join(missing)}",
        )
        return

    bot_token  = os.environ["TELEGRAM_BOT_TOKEN"]
    api_id     = int(os.environ["TELEGRAM_API_ID"])
    api_hash   = os.environ["TELEGRAM_API_HASH"]
    channel_id = int(os.environ["CHANNEL_ID"])

    # ── Phase 1: connecting ────────────────────────────────────────────────────
    await query.edit_message_text(
        "📥 *در حال اتصال به کانال…*\n\n"
        "⏳ لطفاً صبر کنید.",
        parse_mode="Markdown",
    )

    try:
        from channel_history.collector import collect_channel_history
        groups = await collect_channel_history(
            bot_token=bot_token,
            api_id=api_id,
            api_hash=api_hash,
            channel_id=channel_id,
        )
    except Exception as exc:
        logger.exception("channel_import_panel | collect failed: %s", exc)
        await query.edit_message_text(
            f"❌ *خطا در اتصال به کانال*\n\n<code>{exc}</code>",
            parse_mode="HTML",
        )
        return

    if not groups:
        await query.edit_message_text(
            "📭 *هیچ پیامی در کانال یافت نشد.*",
            parse_mode="Markdown",
        )
        return

    total_msgs = sum(len(g.message_ids) for g in groups)

    # ── Phase 2: importing ─────────────────────────────────────────────────────
    await query.edit_message_text(
        f"📥 *در حال ایمپورت…*\n\n"
        f"📨 پیام‌های دریافت‌شده: *{total_msgs}*\n"
        f"📦 گروه‌های ویلا: *{len(groups)}*\n\n"
        "⏳ در حال ذخیره‌سازی در پایگاه داده…",
        parse_mode="Markdown",
    )

    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, _sync_import, groups)
    except Exception as exc:
        logger.exception("channel_import_panel | import pipeline failed: %s", exc)
        await query.edit_message_text(
            f"❌ *خطا در ایمپورت*\n\n<code>{exc}</code>",
            parse_mode="HTML",
        )
        return

    # ── Phase 3: summary ───────────────────────────────────────────────────────
    created = sum(1 for r in results if r.success and r.mode == "create")
    updated = sum(1 for r in results if r.success and r.mode == "update")
    failed  = [r for r in results if not r.success]
    skipped = len(groups) - len(results)

    logger.info(
        "channel_import_panel | complete: msgs=%d groups=%d "
        "created=%d updated=%d failed=%d skipped=%d",
        total_msgs, len(groups), created, updated, len(failed), skipped,
    )

    fail_section = ""
    if failed:
        items = "\n".join(
            f"  • {r.villa_code or '—'}: {r.error or 'خطای ناشناخته'}"
            for r in failed[:10]
        )
        if len(failed) > 10:
            items += f"\n  … و {len(failed) - 10} مورد دیگر"
        fail_section = f"\n\n❌ *جزئیات خطاها:*\n{items}"

    summary = (
        "📊 *خلاصه ایمپورت کانال*\n\n"
        f"📨 پیام‌های بررسی‌شده: *{total_msgs}*\n"
        f"📦 گروه‌های پردازش‌شده: *{len(groups)}*\n"
        f"⏭ رد‌شده (بدون متن): *{skipped}*\n\n"
        f"✅ ویلاهای جدید: *{created}*\n"
        f"🔄 ویلاهای به‌روزشده: *{updated}*\n"
        f"❌ خطا: *{len(failed)}*"
        f"{fail_section}"
    )

    await query.edit_message_text(summary, parse_mode="Markdown")


# ── Sync import helper (runs in executor thread) ───────────────────────────────

def _sync_import(groups) -> list:
    """
    Run the parse → upsert pipeline synchronously.

    Mirrors channel_history/importer.import_villa_groups but without async
    overhead, so it can be safely called from run_in_executor without
    nesting event loops.
    """
    from smart_import.parser import parse_villa_text
    from smart_import.importer import import_villa_from_channel

    results = []
    for idx, group in enumerate(groups):
        if not group.text:
            logger.debug(
                "channel_import_panel | group %d (msg_id=%d): no text — skipped",
                idx, group.telegram_message_id,
            )
            continue

        data = parse_villa_text(group.text)
        data.photos                  = list(group.photo_file_ids)
        data.telegram_message_id     = group.telegram_message_id
        data.telegram_media_group_id = group.telegram_media_group_id
        data.original_caption        = group.original_caption

        result = import_villa_from_channel(data)

        if result.success:
            logger.info(
                "channel_import_panel | group %d (msg_id=%d): %s villa %s  "
                "city=%s  price=%s  photos=%d",
                idx, group.telegram_message_id, result.mode, result.villa_code,
                data.city or "—",
                f"{(data.price or 0) / 1e9:.2f}B" if data.price else "—",
                len(group.photo_file_ids),
            )
        else:
            logger.warning(
                "channel_import_panel | group %d (msg_id=%d): FAILED — %s",
                idx, group.telegram_message_id, result.error,
            )

        results.append(result)

    return results
