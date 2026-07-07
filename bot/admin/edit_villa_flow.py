"""
Edit Villa flow — admin types an MV code, the bot loads the full villa record,
lets the admin change any field(s), then saves with PUT (update, not create).

Entry : "✏️ ویرایش ویلا" keyboard button
States: EV_WAITING_CODE → EV_PREVIEW ↔ EV_EDIT_FIELD → EV_EDIT_VALUE → EV_PREVIEW
        EV_PREVIEW → EV_PHOTOS → save → END

Design rules:
  • The VillaData object is created ONCE (full copy from DB) and mutated
    in-place — unedited fields are NEVER reset.
  • Save always calls import_villa(data, mode="update") — never "create".
  • This module does NOT touch smart_import_flow.py or channel_importer.py.
"""
from __future__ import annotations

import copy
import dataclasses
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
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

from config import ADMIN_ID
from keyboards import get_main_keyboard, admin_panel_keyboard
from smart_import.importer import import_villa
from smart_import.models import VillaData
from states import EV_WAITING_CODE, EV_PREVIEW, EV_EDIT_FIELD, EV_EDIT_VALUE, EV_PHOTOS

logger = logging.getLogger(__name__)


# ── Persian digit normalisation ───────────────────────────────────────────────

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _to_latin(text: str) -> str:
    return text.translate(_DIGIT_TABLE)


# ── Editable field definitions (same set as smart import) ────────────────────
# (field_name, label, value_type)

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
    ("document_type",   "📄 نوع سند",         "str"),
    ("description",     "📝 توضیحات",         "str"),
]

_FIELD_MAP: dict[str, tuple[str, str]] = {
    f: (label, vtype) for f, label, vtype in EDITABLE_FIELDS
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID


def _yn(val: int) -> str:
    return "✅ بله" if val else "❌ خیر"


def _fmt_price(price: float | None) -> str:
    if price is None:
        return "—"
    b = price / 1_000_000_000
    if b == int(b):
        return f"{int(b)} میلیارد"
    return f"{b:.2f} میلیارد"


def _build_preview(data: VillaData, photo_count: int | None = None) -> str:
    doc_str = "، ".join(data.documents) if data.documents else "—"
    photos_note = ""
    if photo_count is None:
        photo_count = len(data.photos)
    if photo_count:
        photos_note = f"\n📷 عکس‌ها: {photo_count} فایل"
    return (
        f"📋 *پیش‌نمایش ویرایش ویلا*\n\n"
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
        f"{photos_note}"
    )


def _preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ذخیره تغییرات", callback_data="ev_confirm"),
            InlineKeyboardButton("✏️ ویرایش فیلدها", callback_data="ev_edit"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="ev_cancel")],
    ])


def _edit_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for field, label, _ in EDITABLE_FIELDS:
        row.append(InlineKeyboardButton(label, callback_data=f"ev_field_{field}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ بازگشت به پیش‌نمایش", callback_data="ev_back")])
    return InlineKeyboardMarkup(rows)


_PHOTOS_KB = ReplyKeyboardMarkup(
    [["✅ ذخیره ویلا"], ["⏭ بدون تغییر عکس‌ها"]],
    resize_keyboard=True,
)


# ── DB row → VillaData conversion ─────────────────────────────────────────────

def _row_to_villa_data(row: dict) -> VillaData:
    """Convert an API villa dict to a VillaData instance (deep copy of all fields)."""
    doc_str   = row.get("document_type") or ""
    documents = [s.strip() for s in doc_str.replace(",", "،").split("،") if s.strip()]

    photos_str = row.get("photos") or ""
    photos     = [s.strip() for s in photos_str.split(",") if s.strip()]

    return VillaData(
        villa_code      = row.get("villa_code"),
        city            = row.get("city"),
        area_type       = row.get("area_type"),
        price           = row.get("price"),
        land_size       = row.get("land_size"),
        building_size   = row.get("building_size"),
        bedrooms        = row.get("bedrooms"),
        master_bedrooms = row.get("master_bedrooms"),
        has_pool        = int(row.get("has_pool") or 0),
        has_jacuzzi     = int(row.get("has_jacuzzi") or 0),
        has_roof_garden = int(row.get("has_roof_garden") or 0),
        has_parking     = int(row.get("has_parking") or 0),
        has_storage     = int(row.get("has_storage") or 0),
        documents       = documents,
        description     = row.get("description") or "",
        photos          = photos,
    )


# ── Step 1: entry ─────────────────────────────────────────────────────────────

async def start_edit_villa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return ConversationHandler.END

    context.user_data.pop("ev_data", None)
    context.user_data.pop("ev_edit_field", None)
    context.user_data.pop("ev_new_photos", None)

    await update.message.reply_text(
        "✏️ *ویرایش ویلا*\n\n"
        "کد ویلا را وارد کنید (مثلاً MV-0042):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return EV_WAITING_CODE


# ── Step 2: receive MV code, fetch, show preview ──────────────────────────────

async def handle_villa_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_code = update.message.text.strip().upper()

    # Accept both "MV-42" and "42" as shorthand
    if raw_code.isdigit():
        raw_code = f"MV-{int(raw_code):04d}"
    elif not raw_code.startswith("MV-"):
        await update.message.reply_text(
            "⚠️ فرمت کد معتبر نیست.\n"
            "لطفاً به شکل *MV-0042* وارد کنید:",
            parse_mode="Markdown",
        )
        return EV_WAITING_CODE

    from pg_villas import get_villa_by_code

    loading_msg = await update.message.reply_text("🔍 در حال جستجو…")

    row = get_villa_by_code(raw_code)
    await loading_msg.delete()

    if row is None:
        await update.message.reply_text(
            f"❌ ویلا با کد *{raw_code}* یافت نشد.\n"
            "کد دیگری وارد کنید یا /cancel بزنید:",
            parse_mode="Markdown",
        )
        return EV_WAITING_CODE

    data = _row_to_villa_data(row)
    context.user_data["ev_data"] = data

    logger.info(
        "edit_villa: loaded code=%s id=%s city=%s price=%s photos=%d",
        data.villa_code, row.get("id"), data.city, data.price, len(data.photos),
    )

    await update.message.reply_text(
        _build_preview(data),
        parse_mode="Markdown",
        reply_markup=_preview_keyboard(),
    )
    return EV_PREVIEW


# ── Step 3a: confirm → collect photos ────────────────────────────────────────

async def cb_ev_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data: VillaData | None = context.user_data.get("ev_data")
    if data is None:
        await query.edit_message_text("❌ داده‌ای یافت نشد. لطفاً دوباره شروع کنید.")
        return ConversationHandler.END

    context.user_data["ev_new_photos"] = []
    existing_count = len(data.photos)

    note = (
        f"در حال حاضر *{existing_count} عکس* ذخیره است.\n"
        "عکس‌های جدید ارسال کنید تا جایگزین شوند، یا\n"
        "«⏭ بدون تغییر عکس‌ها» را بزنید تا عکس‌های فعلی حفظ شوند."
        if existing_count
        else "عکسی ذخیره نشده. می‌توانید عکس ارسال کنید یا «⏭ بدون تغییر عکس‌ها» بزنید."
    )

    await query.edit_message_text(
        f"📷 *مدیریت عکس‌ها*\n\n{note}",
        parse_mode="Markdown",
    )
    await context.bot.send_message(
        update.effective_user.id,
        "📷 عکس‌ها را ارسال کنید یا مستقیم ذخیره کنید:",
        reply_markup=_PHOTOS_KB,
    )
    return EV_PHOTOS


# ── Step 3a-i: new photo received ────────────────────────────────────────────

async def handle_ev_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_id = update.message.photo[-1].file_id
    new_photos: list = context.user_data.setdefault("ev_new_photos", [])
    new_photos.append(file_id)
    await update.message.reply_text(
        f"✅ عکس {len(new_photos)} دریافت شد.",
        reply_markup=_PHOTOS_KB,
    )
    return EV_PHOTOS


# ── Step 3a-ii: save (with optional new photos replacing old ones) ────────────

async def handle_ev_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data: VillaData | None = context.user_data.get("ev_data")
    if data is None:
        await update.message.reply_text(
            "❌ خطای داخلی. لطفاً دوباره شروع کنید.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END

    new_photos: list = context.user_data.get("ev_new_photos", [])
    if new_photos:
        data.photos = new_photos   # replace with newly uploaded set
    # else: data.photos already holds the originals loaded from DB — no change

    result = import_villa(data, mode="update")
    context.user_data.clear()

    if result.success:
        photo_note = f"  |  {len(data.photos)} عکس" if data.photos else ""
        await update.message.reply_text(
            f"✅ ویلا *{result.villa_code}* به‌روز شد{photo_note}.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
    else:
        await update.message.reply_text(
            f"❌ خطا در ذخیره:\n{result.error}",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
    return ConversationHandler.END


# ── Step 3a-iii: skip photos → keep existing ─────────────────────────────────

async def handle_ev_skip_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Discard any in-progress new_photos and save with the originals
    context.user_data["ev_new_photos"] = []
    return await handle_ev_save(update, context)


# ── Step 3b: cancel ───────────────────────────────────────────────────────────

async def cb_ev_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ ویرایش ویلا لغو شد.")
    await context.bot.send_message(
        update.effective_user.id,
        "بازگشت به منو.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


# ── Step 3c: open edit menu ───────────────────────────────────────────────────

async def cb_ev_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ *ویرایش فیلد*\n\nکدام فیلد را می‌خواهید ویرایش کنید؟",
        parse_mode="Markdown",
        reply_markup=_edit_keyboard(),
    )
    return EV_EDIT_FIELD


# ── Step 4: field selected → toggle (bool) or ask for value ──────────────────

async def cb_ev_field_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    field = query.data.removeprefix("ev_field_")
    if field not in _FIELD_MAP:
        await query.answer("فیلد نامعتبر")
        return EV_EDIT_FIELD

    label, vtype = _FIELD_MAP[field]
    data: VillaData = context.user_data["ev_data"]

    if field == "document_type":
        current = "، ".join(data.documents) if data.documents else ""
    else:
        current = getattr(data, field)

    if vtype == "bool":
        # Toggle in-place — no text input needed
        setattr(data, field, 0 if current else 1)
        await query.edit_message_text(
            _build_preview(data),
            parse_mode="Markdown",
            reply_markup=_preview_keyboard(),
        )
        return EV_PREVIEW

    context.user_data["ev_edit_field"] = field
    current_str = str(current) if current is not None else "—"
    await query.edit_message_text(
        f"✏️ *{label}*\n\nمقدار فعلی: `{current_str}`\n\nمقدار جدید را وارد کنید:",
        parse_mode="Markdown",
    )
    return EV_EDIT_VALUE


# ── Step 4b: back to preview ──────────────────────────────────────────────────

async def cb_ev_back_to_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data: VillaData | None = context.user_data.get("ev_data")
    if data is None:
        await query.edit_message_text("❌ داده‌ای یافت نشد.")
        return ConversationHandler.END
    await query.edit_message_text(
        _build_preview(data),
        parse_mode="Markdown",
        reply_markup=_preview_keyboard(),
    )
    return EV_PREVIEW


# ── Step 5: receive new value ─────────────────────────────────────────────────

async def handle_ev_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("ev_edit_field")
    data: VillaData | None = context.user_data.get("ev_data")

    if not field or data is None:
        await update.message.reply_text("❌ خطای داخلی. لطفاً دوباره شروع کنید.")
        return ConversationHandler.END

    label, vtype = _FIELD_MAP[field]
    raw = update.message.text.strip()
    raw_latin = _to_latin(raw).replace(",", "").replace("،", "")

    # ── document_type: virtual field backed by data.documents ────────────────
    if field == "document_type":
        if raw and raw != "—":
            data.documents = [s.strip() for s in raw.replace(",", "،").split("،") if s.strip()]
        else:
            data.documents = []
        context.user_data.pop("ev_edit_field", None)
        await update.message.reply_text(
            f"✅ *📄 نوع سند* به‌روز شد.\n\n" + _build_preview(data),
            parse_mode="Markdown",
            reply_markup=_preview_keyboard(),
        )
        return EV_PREVIEW

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
        return EV_EDIT_VALUE

    setattr(data, field, new_val)
    context.user_data.pop("ev_edit_field", None)

    await update.message.reply_text(
        f"✅ *{label}* به‌روز شد.\n\n" + _build_preview(data),
        parse_mode="Markdown",
        reply_markup=_preview_keyboard(),
    )
    return EV_PREVIEW


# ── Non-text guard for EV_WAITING_CODE ───────────────────────────────────────

async def _prompt_code_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "⚠️ لطفاً کد ویلا را به صورت متن وارد کنید (مثلاً MV-0042)."
    )
    return EV_WAITING_CODE


# ── Cancel command ─────────────────────────────────────────────────────────────

async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ ویرایش ویلا لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


# ── ConversationHandler factory ───────────────────────────────────────────────

def build_edit_villa_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ ویرایش ویلا$"), start_edit_villa),
        ],
        states={
            EV_WAITING_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_villa_code),
                MessageHandler(~filters.COMMAND, _prompt_code_only),
            ],
            EV_PREVIEW: [
                CallbackQueryHandler(cb_ev_confirm, pattern="^ev_confirm$"),
                CallbackQueryHandler(cb_ev_cancel,  pattern="^ev_cancel$"),
                CallbackQueryHandler(cb_ev_edit,    pattern="^ev_edit$"),
            ],
            EV_EDIT_FIELD: [
                CallbackQueryHandler(cb_ev_field_selected,  pattern="^ev_field_"),
                CallbackQueryHandler(cb_ev_back_to_preview, pattern="^ev_back$"),
            ],
            EV_EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ev_edit_value),
            ],
            EV_PHOTOS: [
                MessageHandler(filters.PHOTO, handle_ev_photo),
                MessageHandler(filters.Regex("^✅ ذخیره ویلا$"),         handle_ev_save),
                MessageHandler(filters.Regex("^⏭ بدون تغییر عکس‌ها$"), handle_ev_skip_photos),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
        ],
        per_message=False,
    )
