"""
Notification preferences — lets users subscribe to new villa alerts.

Flow (inline keyboards throughout):
  Entry → show current prefs (if any) or start setup
  Setup  NP_REGION → NP_PRICE → NP_TYPE → save → confirm

All steps use callback queries so no new text messages are created.
"""
from __future__ import annotations

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

from database import (
    get_notification_prefs,
    save_notification_prefs,
    deactivate_notification_prefs,
)
from keyboards import get_main_keyboard
from states import NP_REGION, NP_PRICE, NP_TYPE
from utils import fmt_price

# ── Price range definitions (min, max, label) ──────────────────────────────────

PRICE_RANGES: list[tuple[str, float | None, float | None]] = [
    ("همه قیمت‌ها",              None,           None          ),
    ("اقتصادی — زیر ۷ میلیارد",  None,           7_000_000_000 ),
    ("متوسط — ۷ تا ۱۵ میلیارد",  7_000_000_000,  15_000_000_000),
    ("لوکس — بالای ۱۵ میلیارد",  15_000_000_000, None          ),
]


# ── Keyboard builders ──────────────────────────────────────────────────────────

def _region_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 همه مناطق",  callback_data="np_region_all")],
        [InlineKeyboardButton("🏖 ساحلی",      callback_data="np_region_ساحلی")],
        [InlineKeyboardButton("🌲 جنگلی",      callback_data="np_region_جنگلی")],
        [InlineKeyboardButton("❌ لغو",         callback_data="np_cancel")],
    ])


def _price_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"np_price_{i}")]
        for i, (label, _, _) in enumerate(PRICE_RANGES)
    ]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="np_back_region")])
    return InlineKeyboardMarkup(rows)


def _type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏡 همه انواع",  callback_data="np_type_all")],
        [InlineKeyboardButton("🏠 مستقل",      callback_data="np_type_مستقل")],
        [InlineKeyboardButton("🏘 شهرکی",      callback_data="np_type_شهرکی")],
        [InlineKeyboardButton("🔙 بازگشت",     callback_data="np_back_price")],
    ])


def _prefs_summary_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش ترجیحات",      callback_data="np_edit")],
        [InlineKeyboardButton("🔕 غیرفعال کردن اعلان‌ها", callback_data="notif_disable")],
    ])


# ── Text helpers ───────────────────────────────────────────────────────────────

def _describe_prefs(prefs: dict) -> str:
    area  = prefs.get("area_type") or "همه مناطق"
    vtype = prefs.get("villa_type") or "همه انواع"

    min_p = prefs.get("min_price")
    max_p = prefs.get("max_price")
    if min_p is None and max_p is None:
        price_str = "همه قیمت‌ها"
    elif min_p is None:
        price_str = f"تا {fmt_price(max_p)}"
    elif max_p is None:
        price_str = f"از {fmt_price(min_p)}"
    else:
        price_str = f"{fmt_price(min_p)} تا {fmt_price(max_p)}"

    return (
        f"🔔 *اعلان‌های شما فعال است*\n\n"
        f"🌊 منطقه: {area}\n"
        f"💰 بازه قیمت: {price_str}\n"
        f"🏡 نوع ویلا: {vtype}\n\n"
        f"_هر بار که ویلایی با این مشخصات ثبت شود، به شما اطلاع داده می‌شود._"
    )


# ── Entry handlers ─────────────────────────────────────────────────────────────

async def start_notify_prefs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry from the 🔔 menu button."""
    user_id = update.effective_user.id
    prefs   = get_notification_prefs(user_id)

    if prefs and prefs.get("active"):
        await update.message.reply_text(
            _describe_prefs(prefs),
            parse_mode="Markdown",
            reply_markup=_prefs_summary_kb(),
        )
        return ConversationHandler.END

    # No active prefs → start setup
    await update.message.reply_text(
        "🔔 *تنظیم اعلان ویلاهای جدید*\n\n"
        "هر بار که ویلایی با مشخصات شما ثبت شود به شما اطلاع می‌دهیم.\n\n"
        "منطقه مورد نظر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_region_kb(),
    )
    return NP_REGION


async def cb_np_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Edit button from the prefs summary — restart setup."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔔 *ویرایش ترجیحات اعلان*\n\n"
        "منطقه مورد نظر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_region_kb(),
    )
    return NP_REGION


# ── Step 1: region ─────────────────────────────────────────────────────────────

async def cb_np_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data  = query.data  # np_region_all | np_region_ساحلی | np_region_جنگلی

    if data == "np_cancel":
        await query.edit_message_text("❌ تنظیم اعلان لغو شد.")
        return ConversationHandler.END

    area = None if data == "np_region_all" else data.split("np_region_")[1]
    context.user_data["np_area_type"] = area

    await query.edit_message_text(
        "💰 بازه قیمتی مورد نظر را انتخاب کنید:",
        reply_markup=_price_kb(),
    )
    return NP_PRICE


# ── Step 2: price ──────────────────────────────────────────────────────────────

async def cb_np_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "np_back_region":
        await query.edit_message_text(
            "🌊 منطقه مورد نظر را انتخاب کنید:",
            reply_markup=_region_kb(),
        )
        return NP_REGION

    idx = int(data.split("np_price_")[1])
    _, min_p, max_p = PRICE_RANGES[idx]
    context.user_data["np_min_price"] = min_p
    context.user_data["np_max_price"] = max_p

    await query.edit_message_text(
        "🏡 نوع ویلا را انتخاب کنید:",
        reply_markup=_type_kb(),
    )
    return NP_TYPE


# ── Step 3: villa type → save ──────────────────────────────────────────────────

async def cb_np_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "np_back_price":
        await query.edit_message_text(
            "💰 بازه قیمتی مورد نظر را انتخاب کنید:",
            reply_markup=_price_kb(),
        )
        return NP_PRICE

    vtype = None if data == "np_type_all" else data.split("np_type_")[1]

    area  = context.user_data.get("np_area_type")
    min_p = context.user_data.get("np_min_price")
    max_p = context.user_data.get("np_max_price")

    save_notification_prefs(
        user_id    = query.from_user.id,
        area_type  = area,
        min_price  = min_p,
        max_price  = max_p,
        villa_type = vtype,
    )
    context.user_data.pop("np_area_type",  None)
    context.user_data.pop("np_min_price",  None)
    context.user_data.pop("np_max_price",  None)

    # Build confirmation text
    area_label  = area or "همه مناطق"
    vtype_label = vtype or "همه انواع"
    min_p_label = min_p
    max_p_label = max_p
    if min_p is None and max_p is None:
        price_label = "همه قیمت‌ها"
    elif min_p is None:
        price_label = f"تا {fmt_price(max_p_label)}"
    elif max_p is None:
        price_label = f"از {fmt_price(min_p_label)}"
    else:
        price_label = f"{fmt_price(min_p_label)} تا {fmt_price(max_p_label)}"

    await query.edit_message_text(
        f"✅ *اعلان‌ها با موفقیت تنظیم شد*\n\n"
        f"🌊 منطقه: {area_label}\n"
        f"💰 قیمت: {price_label}\n"
        f"🏡 نوع: {vtype_label}\n\n"
        f"_از این پس، هر ویلای جدید منطبق با ترجیحات شما به شما اطلاع داده می‌شود._",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ── Shared: disable (also used standalone from notification cards) ─────────────

async def cb_notif_disable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles notif_disable callback — works both inside and outside the conv."""
    query   = update.callback_query
    user_id = query.from_user.id
    deactivate_notification_prefs(user_id)
    await query.answer("🔕 اعلان‌های شما غیرفعال شد")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── Cancel / fallback ──────────────────────────────────────────────────────────

async def cancel_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("np_area_type", None)
    context.user_data.pop("np_min_price", None)
    context.user_data.pop("np_max_price", None)
    await update.message.reply_text(
        "❌ تنظیم اعلان لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


# ── ConversationHandler factory ────────────────────────────────────────────────

def build_notify_prefs_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔔 اعلان ویلاهای جدید$"), start_notify_prefs),
            CallbackQueryHandler(cb_np_edit, pattern="^np_edit$"),
        ],
        states={
            NP_REGION: [CallbackQueryHandler(cb_np_region, pattern="^np_region_|^np_cancel$")],
            NP_PRICE:  [CallbackQueryHandler(cb_np_price,  pattern="^np_price_|^np_back_region$")],
            NP_TYPE:   [CallbackQueryHandler(cb_np_type,   pattern="^np_type_|^np_back_price$")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_notify),
            CommandHandler("start",  cancel_notify),
        ],
        per_message=False,
    )
