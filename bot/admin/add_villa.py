from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from config import ADMIN_ID
from database import get_next_villa_code, insert_villa
from keyboards import get_main_keyboard
from states import (
    CITY, AREA_TYPE, PRICE, LAND_SIZE, BUILDING_SIZE, BEDROOMS,
    VILLA_TYPE, FEATURES, DOCUMENT_TYPE, PHOTOS, VIDEO, LOCATION,
    DESCRIPTION, CONFIRM,
    FEATURE_KEYS, FEATURE_QUESTIONS,
)

# ── Options ────────────────────────────────────────────────────────────────────

CITIES = ["محمودآباد", "سرخرود", "ایزدشهر", "نور", "آمل", "چمستان"]
AREA_TYPES = ["ساحلی", "جنگلی"]
VILLA_TYPES = ["شهرکی", "مستقل"]
DOC_TYPES = ["سند تک‌برگ", "سند منگوله‌دار", "وکالتنامه", "قولنامه", "بنچاق"]

# ── Flow keyboards ─────────────────────────────────────────────────────────────

CITY_KB = ReplyKeyboardMarkup(
    [CITIES[:3], CITIES[3:]],
    resize_keyboard=True,
)
AREA_KB = ReplyKeyboardMarkup(
    [[t] for t in AREA_TYPES],
    resize_keyboard=True,
)
YES_NO_KB = ReplyKeyboardMarkup(
    [["بله ✅", "خیر ❌"]],
    resize_keyboard=True,
)
VILLA_TYPE_KB = ReplyKeyboardMarkup(
    [[t] for t in VILLA_TYPES],
    resize_keyboard=True,
)
DOC_TYPE_KB = ReplyKeyboardMarkup(
    [[DOC_TYPES[0], DOC_TYPES[1]], [DOC_TYPES[2], DOC_TYPES[3]], [DOC_TYPES[4]]],
    resize_keyboard=True,
)
PHOTOS_KB = ReplyKeyboardMarkup(
    [["✅ پایان عکس‌ها"]],
    resize_keyboard=True,
)
SKIP_KB = ReplyKeyboardMarkup(
    [["⏭ رد کردن"]],
    resize_keyboard=True,
)
LOCATION_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📍 ارسال موقعیت مکانی", request_location=True)],
        ["⏭ رد کردن"],
    ],
    resize_keyboard=True,
)
CONFIRM_KB = ReplyKeyboardMarkup(
    [["✅ تایید و ثبت"], ["✏️ ویرایش", "❌ لغو"]],
    resize_keyboard=True,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID


def _is_yes(text: str) -> bool:
    return "بله" in text


def _is_no(text: str) -> bool:
    return "خیر" in text


def _build_summary(v: dict) -> str:
    yn = lambda x: "✅ بله" if x else "❌ خیر"
    price_fmt = f"{int(v['price']):,}" if v.get("price") is not None else "-"
    photos_count = len(v.get("photos") or [])
    has_video = "✅ دارد" if v.get("video") else "❌ ندارد"
    has_location = "✅ دارد" if v.get("latitude") is not None else "❌ ندارد"
    desc = v.get("description") or "-"

    return (
        f"🏡 *خلاصه اطلاعات ویلا*\n\n"
        f"📌 کد ویلا: `{v['villa_code']}`\n"
        f"🏙 شهر: {v.get('city', '-')}\n"
        f"🌊 نوع منطقه: {v.get('area_type', '-')}\n"
        f"💰 قیمت: {price_fmt} تومان\n"
        f"📐 متراژ زمین: {v.get('land_size', '-')} متر مربع\n"
        f"🏠 متراژ بنا: {v.get('building_size', '-')} متر مربع\n"
        f"🛏 تعداد اتاق‌خواب: {v.get('bedrooms', '-')}\n"
        f"🏡 نوع ویلا: {'شهرکی' if v.get('is_townhouse') else 'مستقل'}\n"
        f"🏊 استخر: {yn(v.get('has_pool'))}\n"
        f"🛁 جکوزی: {yn(v.get('has_jacuzzi'))}\n"
        f"🌿 روف گاردن: {yn(v.get('has_roof_garden'))}\n"
        f"🚗 پارکینگ: {yn(v.get('has_parking'))}\n"
        f"📦 انباری: {yn(v.get('has_storage'))}\n"
        f"📄 نوع سند: {v.get('document_type', '-')}\n"
        f"🖼 تعداد تصاویر: {photos_count}\n"
        f"🎥 ویدیو: {has_video}\n"
        f"📍 موقعیت مکانی: {has_location}\n"
        f"📝 توضیحات: {desc}"
    )


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ ثبت ویلا لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END

# ── Step handlers ──────────────────────────────────────────────────────────────

async def start_add_villa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return ConversationHandler.END

    code = get_next_villa_code()
    context.user_data["villa"] = {"villa_code": code, "photos": []}
    context.user_data["feature_idx"] = 0

    await update.message.reply_text(
        f"➕ *ثبت ویلای جدید*\n\n"
        f"کد ویلا به‌صورت خودکار تعیین شد: `{code}`\n\n"
        f"لطفاً شهر ویلا را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=CITY_KB,
    )
    return CITY


async def handle_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in CITIES:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:", reply_markup=CITY_KB
        )
        return CITY

    context.user_data["villa"]["city"] = text
    await update.message.reply_text("نوع منطقه را انتخاب کنید:", reply_markup=AREA_KB)
    return AREA_TYPE


async def handle_area_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in AREA_TYPES:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:", reply_markup=AREA_KB
        )
        return AREA_TYPE

    context.user_data["villa"]["area_type"] = text
    await update.message.reply_text(
        "💰 قیمت ویلا را به تومان وارد کنید:\n_(فقط عدد، بدون خط تیره یا کاما)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PRICE


async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", "").replace("،", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ لطفاً فقط عدد وارد کنید:")
        return PRICE

    context.user_data["villa"]["price"] = float(text)
    await update.message.reply_text("📐 متراژ زمین را به متر مربع وارد کنید:")
    return LAND_SIZE


async def handle_land_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text("⚠️ لطفاً فقط عدد وارد کنید:")
        return LAND_SIZE

    context.user_data["villa"]["land_size"] = float(text)
    await update.message.reply_text("🏠 متراژ بنا را به متر مربع وارد کنید:")
    return BUILDING_SIZE


async def handle_building_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text("⚠️ لطفاً فقط عدد وارد کنید:")
        return BUILDING_SIZE

    context.user_data["villa"]["building_size"] = float(text)
    await update.message.reply_text("🛏 تعداد اتاق‌خواب را وارد کنید:")
    return BEDROOMS


async def handle_bedrooms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ لطفاً فقط عدد صحیح وارد کنید:")
        return BEDROOMS

    context.user_data["villa"]["bedrooms"] = int(text)
    await update.message.reply_text("نوع ویلا را انتخاب کنید:", reply_markup=VILLA_TYPE_KB)
    return VILLA_TYPE


async def handle_villa_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in VILLA_TYPES:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:", reply_markup=VILLA_TYPE_KB
        )
        return VILLA_TYPE

    context.user_data["villa"]["is_townhouse"] = 1 if text == "شهرکی" else 0
    context.user_data["feature_idx"] = 0
    await update.message.reply_text(FEATURE_QUESTIONS[0], reply_markup=YES_NO_KB)
    return FEATURES


async def handle_features(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (_is_yes(text) or _is_no(text)):
        idx = context.user_data.get("feature_idx", 0)
        await update.message.reply_text(
            f"لطفاً بله یا خیر را انتخاب کنید:\n{FEATURE_QUESTIONS[idx]}",
            reply_markup=YES_NO_KB,
        )
        return FEATURES

    idx = context.user_data["feature_idx"]
    context.user_data["villa"][FEATURE_KEYS[idx]] = 1 if _is_yes(text) else 0
    idx += 1

    if idx < len(FEATURE_KEYS):
        context.user_data["feature_idx"] = idx
        await update.message.reply_text(FEATURE_QUESTIONS[idx], reply_markup=YES_NO_KB)
        return FEATURES

    await update.message.reply_text(
        "📄 نوع سند ملکی را انتخاب کنید:", reply_markup=DOC_TYPE_KB
    )
    return DOCUMENT_TYPE


async def handle_document_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in DOC_TYPES:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:", reply_markup=DOC_TYPE_KB
        )
        return DOCUMENT_TYPE

    context.user_data["villa"]["document_type"] = text
    await update.message.reply_text(
        "🖼 لطفاً تصاویر ویلا را یک‌به‌یک ارسال کنید.\n"
        "پس از ارسال همه تصاویر دکمه زیر را بزنید:",
        reply_markup=PHOTOS_KB,
    )
    return PHOTOS


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_id = update.message.photo[-1].file_id
    context.user_data["villa"]["photos"].append(file_id)
    count = len(context.user_data["villa"]["photos"])
    await update.message.reply_text(
        f"✅ تصویر {count} دریافت شد. می‌توانید تصویر بعدی را ارسال کنید یا ثبت را پایان دهید.",
        reply_markup=PHOTOS_KB,
    )
    return PHOTOS


async def handle_photos_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🎥 یک ویدیو از ویلا ارسال کنید یا این مرحله را رد کنید:",
        reply_markup=SKIP_KB,
    )
    return VIDEO


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    video = update.message.video or update.message.document
    if video:
        context.user_data["villa"]["video"] = video.file_id
    await update.message.reply_text(
        "📍 موقعیت مکانی ویلا را ارسال کنید یا رد کنید:",
        reply_markup=LOCATION_KB,
    )
    return LOCATION


async def skip_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["villa"]["video"] = None
    await update.message.reply_text(
        "📍 موقعیت مکانی ویلا را ارسال کنید یا رد کنید:",
        reply_markup=LOCATION_KB,
    )
    return LOCATION


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    loc = update.message.location
    context.user_data["villa"]["latitude"] = loc.latitude
    context.user_data["villa"]["longitude"] = loc.longitude
    await update.message.reply_text(
        "📝 توضیحات ویلا را وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DESCRIPTION


async def skip_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["villa"]["latitude"] = None
    context.user_data["villa"]["longitude"] = None
    await update.message.reply_text(
        "📝 توضیحات ویلا را وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DESCRIPTION


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["villa"]["description"] = update.message.text.strip()
    summary = _build_summary(context.user_data["villa"])
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=CONFIRM_KB,
    )
    return CONFIRM


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "✅ تایید و ثبت":
        insert_villa(context.user_data["villa"])
        code = context.user_data["villa"]["villa_code"]
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ ویلا با کد *{code}* با موفقیت ثبت شد.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END

    elif text == "✏️ ویرایش":
        await update.message.reply_text(
            "این بخش در حال توسعه است.", reply_markup=CONFIRM_KB
        )
        return CONFIRM

    elif text == "❌ لغو":
        return await _cancel(update, context)

    await update.message.reply_text(
        "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:", reply_markup=CONFIRM_KB
    )
    return CONFIRM


# ── ConversationHandler factory ────────────────────────────────────────────────

def build_add_villa_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ ثبت ویلا$"), start_add_villa),
        ],
        states={
            CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_city),
            ],
            AREA_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_area_type),
            ],
            PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price),
            ],
            LAND_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_land_size),
            ],
            BUILDING_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_building_size),
            ],
            BEDROOMS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bedrooms),
            ],
            VILLA_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_villa_type),
            ],
            FEATURES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_features),
            ],
            DOCUMENT_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_document_type),
            ],
            PHOTOS: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.Regex("^✅ پایان عکس‌ها$"), handle_photos_done),
            ],
            VIDEO: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video),
                MessageHandler(filters.Regex("^⏭ رد کردن$"), skip_video),
            ],
            LOCATION: [
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.Regex("^⏭ رد کردن$"), skip_location),
            ],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
            ],
            CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
        ],
    )
