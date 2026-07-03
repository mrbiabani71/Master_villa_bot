"""
Smart Import flow — admin pastes a raw villa post, parser extracts data,
admin previews and confirms (or edits field-by-field) before saving.

Entry : "➕ ثبت ویلا" keyboard button
States: SI_WAITING_TEXT → SI_PREVIEW ↔ SI_EDIT_FIELD → SI_EDIT_VALUE → SI_PREVIEW
"""
from __future__ import annotations

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

import logging

from config import ADMIN_ID
from keyboards import get_main_keyboard
from smart_import.parser import parse_villa_text
from smart_import.importer import import_villa
from smart_import.models import VillaData
from states import SI_WAITING_TEXT, SI_PREVIEW, SI_EDIT_FIELD, SI_EDIT_VALUE

logger = logging.getLogger(__name__)


# ── Persian digit normalisation (for user-supplied values) ────────────────────

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _to_latin(text: str) -> str:
    return text.translate(_DIGIT_TABLE)


# ── Editable field definitions ────────────────────────────────────────────────
# (field_name, label, value_type)
# value_type: "str" | "float" | "int" | "bool"

EDITABLE_FIELDS: list[tuple[str, str, str]] = [
    ("villa_code",      "🏷 کد ویلا",         "str"),
    ("city",            "📍 شهر",             "str"),
    ("area_type",       "🌊 نوع منطقه",        "str"),
    ("price",           "💰 قیمت (تومان)",     "float"),
    ("land_size",       "📐 متراژ زمین (م²)",  "float"),
    ("building_size",   "🏠 متراژ بنا (م²)",   "float"),
    ("bedrooms",        "🛏 اتاق‌خواب",        "int"),
    ("master_bedrooms", "🛏 مستر",             "int"),
    ("has_pool",        "🏊 استخر",           "bool"),
    ("has_jacuzzi",     "🛁 جکوزی",          "bool"),
    ("has_roof_garden", "🌿 روف گاردن",       "bool"),
    ("has_parking",     "🚗 پارکینگ",         "bool"),
    ("has_storage",     "📦 انباری",          "bool"),
    ("description",     "📝 توضیحات",         "str"),
]

_FIELD_MAP: dict[str, tuple[str, str]] = {
    f: (label, vtype) for f, label, vtype in EDITABLE_FIELDS
}


# ── Preview builder ───────────────────────────────────────────────────────────

def _yn(val: int) -> str:
    return "✅ بله" if val else "❌ خیر"


def _fmt_price(price: float | None) -> str:
    if price is None:
        return "—"
    b = price / 1_000_000_000
    if b == int(b):
        return f"{int(b)} میلیارد"
    return f"{b:.2f} میلیارد"


def _build_preview(data: VillaData) -> str:
    doc_str = "، ".join(data.documents) if data.documents else "—"
    return (
        f"📋 *پیش‌نمایش ویلا*\n\n"
        f"🏷 کد ویلا: `{data.villa_code or '(خودکار)'}`\n"
        f"📍 شهر: {data.city or '—'}\n"
        f"🌊 نوع منطقه: {data.area_type or '—'}\n"
        f"💰 قیمت: {_fmt_price(data.price)}\n"
        f"📐 متراژ زمین: {data.land_size or '—'} م²\n"
        f"🏠 متراژ بنا: {data.building_size or '—'} م²\n"
        f"🛏 اتاق‌خواب: {data.bedrooms or '—'}\n"
        f"🛏 مستر: {data.master_bedrooms or '—'}\n"
        f"🏊 استخر: {_yn(data.has_pool)}\n"
        f"🛁 جکوزی: {_yn(data.has_jacuzzi)}\n"
        f"🌿 روف گاردن: {_yn(data.has_roof_garden)}\n"
        f"🚗 پارکینگ: {_yn(data.has_parking)}\n"
        f"📦 انباری: {_yn(data.has_storage)}\n"
        f"📄 سند: {doc_str}\n"
        f"📝 توضیحات: {data.description or '—'}"
    )


def _preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید و ذخیره", callback_data="si_confirm"),
            InlineKeyboardButton("✏️ ویرایش فیلدها", callback_data="si_edit"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="si_cancel")],
    ])


def _edit_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for field, label, _ in EDITABLE_FIELDS:
        row.append(InlineKeyboardButton(label, callback_data=f"si_field_{field}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ بازگشت به پیش‌نمایش", callback_data="si_back")])
    return InlineKeyboardMarkup(rows)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID


# ── Step 1: entry ─────────────────────────────────────────────────────────────

async def start_smart_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return ConversationHandler.END

    context.user_data.pop("si_data", None)
    context.user_data.pop("si_edit_field", None)

    await update.message.reply_text(
        "📥 *ثبت هوشمند ویلا*\n\n"
        "متن آگهی ویلا را کپی و ارسال کنید.\n"
        "ربات اطلاعات را به‌صورت خودکار استخراج می‌کند.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SI_WAITING_TEXT


# ── Step 2: receive text, parse, show preview ─────────────────────────────────

async def handle_import_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    logger.debug(
        "SMART_IMPORT | raw text (%d chars, %d lines):\n%s",
        len(text), len(text.splitlines()), text,
    )

    data = parse_villa_text(text)
    context.user_data["si_data"] = data

    logger.debug(
        "SMART_IMPORT | extracted fields:\n"
        "  villa_code     = %s\n"
        "  city           = %s\n"
        "  area_type      = %s\n"
        "  price          = %s\n"
        "  land_size      = %s\n"
        "  building_size  = %s\n"
        "  bedrooms       = %s\n"
        "  master_bedrooms= %s\n"
        "  has_pool       = %s\n"
        "  has_jacuzzi    = %s\n"
        "  has_roof_garden= %s\n"
        "  has_parking    = %s\n"
        "  has_storage    = %s\n"
        "  documents      = %s\n"
        "  description    = %r",
        data.villa_code, data.city, data.area_type, data.price,
        data.land_size, data.building_size, data.bedrooms, data.master_bedrooms,
        data.has_pool, data.has_jacuzzi, data.has_roof_garden,
        data.has_parking, data.has_storage,
        data.documents, data.description,
    )

    missing = []
    if data.city is None:
        missing.append("city (no known city name found in text)")
    if data.price is None:
        missing.append("price (no میلیارد/میلیون/قیمت line found)")
    if missing:
        logger.warning(
            "SMART_IMPORT | missing fields — %s", " | ".join(missing)
        )
    else:
        logger.debug("SMART_IMPORT | all required fields present")

    preview = _build_preview(data)
    await update.message.reply_text(
        preview,
        parse_mode="Markdown",
        reply_markup=_preview_keyboard(),
    )
    return SI_PREVIEW


# ── Step 3a: confirm → save ───────────────────────────────────────────────────

async def cb_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data: VillaData | None = context.user_data.get("si_data")
    if data is None:
        await query.edit_message_text("❌ داده‌ای یافت نشد. لطفاً دوباره شروع کنید.")
        return ConversationHandler.END

    result = import_villa(data, mode="create")

    if result.success:
        context.user_data.clear()
        await query.edit_message_text(
            f"✅ ویلا با کد *{result.villa_code}* با موفقیت ذخیره شد.",
            parse_mode="Markdown",
        )
        await context.bot.send_message(
            update.effective_user.id,
            "می‌توانید ویلای جدیدی ثبت کنید.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END
    else:
        await query.edit_message_text(
            f"❌ خطا در ذخیره:\n{result.error}",
            reply_markup=_preview_keyboard(),
        )
        return SI_PREVIEW


# ── Step 3b: cancel ───────────────────────────────────────────────────────────

async def cb_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ ثبت ویلا لغو شد.")
    await context.bot.send_message(
        update.effective_user.id,
        "بازگشت به منو.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


# ── Step 3c: open edit menu ───────────────────────────────────────────────────

async def cb_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ *ویرایش فیلد*\n\nکدام فیلد را می‌خواهید ویرایش کنید؟",
        parse_mode="Markdown",
        reply_markup=_edit_keyboard(),
    )
    return SI_EDIT_FIELD


# ── Step 4: field selected → toggle (bool) or ask for value ──────────────────

async def cb_field_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    field = query.data.removeprefix("si_field_")
    if field not in _FIELD_MAP:
        await query.answer("فیلد نامعتبر")
        return SI_EDIT_FIELD

    label, vtype = _FIELD_MAP[field]
    data: VillaData = context.user_data["si_data"]
    current = getattr(data, field)

    if vtype == "bool":
        # Toggle immediately — no text input needed
        setattr(data, field, 0 if current else 1)
        preview = _build_preview(data)
        await query.edit_message_text(
            preview,
            parse_mode="Markdown",
            reply_markup=_preview_keyboard(),
        )
        return SI_PREVIEW

    context.user_data["si_edit_field"] = field
    current_str = str(current) if current is not None else "—"
    await query.edit_message_text(
        f"✏️ *{label}*\n\nمقدار فعلی: `{current_str}`\n\nمقدار جدید را وارد کنید:",
        parse_mode="Markdown",
    )
    return SI_EDIT_VALUE


# ── Step 4b: back to preview ─────────────────────────────────────────────────

async def cb_back_to_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data: VillaData | None = context.user_data.get("si_data")
    if data is None:
        await query.edit_message_text("❌ داده‌ای یافت نشد.")
        return ConversationHandler.END
    await query.edit_message_text(
        _build_preview(data),
        parse_mode="Markdown",
        reply_markup=_preview_keyboard(),
    )
    return SI_PREVIEW


# ── Step 5: receive new value ─────────────────────────────────────────────────

async def handle_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("si_edit_field")
    data: VillaData | None = context.user_data.get("si_data")

    if not field or data is None:
        await update.message.reply_text("❌ خطای داخلی. لطفاً دوباره شروع کنید.")
        return ConversationHandler.END

    label, vtype = _FIELD_MAP[field]
    raw = update.message.text.strip()
    raw_latin = _to_latin(raw).replace(",", "").replace("،", "")

    error: str | None = None
    new_val = None

    if vtype == "str":
        new_val = raw if raw and raw != "—" else None
    elif vtype == "float":
        try:
            new_val = float(raw_latin)
        except ValueError:
            error = "⚠️ لطفاً یک عدد معتبر وارد کنید."
    elif vtype == "int":
        try:
            new_val = int(raw_latin)
        except ValueError:
            error = "⚠️ لطفاً یک عدد صحیح وارد کنید."

    if error:
        current_str = str(getattr(data, field, None) or "—")
        await update.message.reply_text(
            f"{error}\n\nمقدار فعلی: `{current_str}`\nمقدار جدید را وارد کنید:",
            parse_mode="Markdown",
        )
        return SI_EDIT_VALUE

    setattr(data, field, new_val)
    context.user_data.pop("si_edit_field", None)

    await update.message.reply_text(
        f"✅ *{label}* به‌روز شد.\n\n" + _build_preview(data),
        parse_mode="Markdown",
        reply_markup=_preview_keyboard(),
    )
    return SI_PREVIEW


# ── Cancel command ────────────────────────────────────────────────────────────

async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ ثبت ویلا لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


# ── ConversationHandler factory ───────────────────────────────────────────────

def build_smart_import_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ ثبت ویلا$"), start_smart_import),
        ],
        states={
            SI_WAITING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_import_text),
            ],
            SI_PREVIEW: [
                CallbackQueryHandler(cb_confirm, pattern="^si_confirm$"),
                CallbackQueryHandler(cb_cancel,  pattern="^si_cancel$"),
                CallbackQueryHandler(cb_edit,    pattern="^si_edit$"),
            ],
            SI_EDIT_FIELD: [
                CallbackQueryHandler(cb_field_selected,  pattern="^si_field_"),
                CallbackQueryHandler(cb_back_to_preview, pattern="^si_back$"),
            ],
            SI_EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_value),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
        ],
        per_message=False,
    )
