from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

from pg_villas import search_villas, get_villa_by_id
from keyboards import get_main_keyboard
from states import BROWSE_AREA, BROWSE_BUDGET
from utils import fmt_price, price_category

# ── Constants ──────────────────────────────────────────────────────────────────

BACK = "🔙 بازگشت"

AREA_TYPE_LABELS = [
    "🏖 ساحلی  (محمودآباد، ایزدشهر، سرخرود)",
    "🌲 جنگلی  (نور، آمل، چمستان)",
]
AREA_TYPE_MAP = {
    "🏖 ساحلی  (محمودآباد، ایزدشهر، سرخرود)": "ساحلی",
    "🌲 جنگلی  (نور، آمل، چمستان)": "جنگلی",
}

BUDGETS: list[tuple[str, float, float | None]] = [
    ("🟢 اقتصادی    (زیر ۷ میلیارد)",         0,              7_000_000_000),
    ("🔵 متوسط      (۷ تا ۱۰ میلیارد)",       7_000_000_000,  10_000_000_000),
    ("🟣 نیمه لوکس  (۱۰ تا ۱۵ میلیارد)",     10_000_000_000, 15_000_000_000),
    ("🔴 لوکس       (بالای ۱۵ میلیارد)",      15_000_000_000, None),
]
BUDGET_LABELS = [b[0] for b in BUDGETS]
BUDGET_MAP    = {b[0]: (b[1], b[2]) for b in BUDGETS}

# ── Keyboards ──────────────────────────────────────────────────────────────────

BROWSE_AREA_KB = ReplyKeyboardMarkup(
    [[label] for label in AREA_TYPE_LABELS] + [[BACK]],
    resize_keyboard=True,
)

BROWSE_BUDGET_KB = ReplyKeyboardMarkup(
    [[label] for label in BUDGET_LABELS] + [[BACK]],
    resize_keyboard=True,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _villa_type(villa: dict) -> str:
    return "شهرکی" if villa.get("is_townhouse") else "مستقل"


def _photos_list(villa: dict) -> list[str]:
    return [p for p in (villa.get("photos") or "").split(",") if p]


def _feature_parts(villa: dict) -> list[str]:
    parts = []
    if villa.get("has_pool"):        parts.append("🏊 استخر")
    if villa.get("has_jacuzzi"):     parts.append("🛁 جکوزی")
    if villa.get("has_roof_garden"): parts.append("🌿 روف گاردن")
    if villa.get("has_parking"):     parts.append("🚗 پارکینگ")
    if villa.get("has_storage"):     parts.append("📦 انباری")
    return parts


def _villa_card(villa: dict, idx: int, total: int) -> str:
    features      = _feature_parts(villa)
    features_line = "  |  ".join(features) if features else "—"

    raw_desc = (villa.get("description") or "").strip()
    desc     = raw_desc[:160] + ("..." if len(raw_desc) > 160 else "")

    price    = fmt_price(villa.get("price"))
    category = price_category(villa.get("price"))

    return (
        f"🏡 *ویلا {villa['villa_code']}*   _({idx + 1} از {total})_\n"
        f"\n"
        f"📍 {villa.get('city', '—')}  ·  🌊 {villa.get('area_type', '—')}  ·  🏠 {_villa_type(villa)}\n"
        f"💰 {price}   {category}\n"
        f"\n"
        f"📐 زمین: {villa.get('land_size', '—')} م²   بنا: {villa.get('building_size', '—')} م²   🛏 {villa.get('bedrooms', '—')} خواب\n"
        f"✨ {features_line}\n"
        f"\n"
        f"📝 _{desc}_"
    )


def _villa_full_detail(villa: dict) -> str:
    features = _feature_parts(villa)
    features_block = "\n".join(f"  ✅ {f}" for f in features) if features else "  —"

    photos    = _photos_list(villa)
    has_video = "✅ دارد" if villa.get("video") else "❌ ندارد"
    has_loc   = "✅ دارد" if villa.get("latitude") is not None else "❌ ندارد"

    desc = (villa.get("description") or "—").strip()

    text = (
        f"📋 *مشخصات کامل — ویلا {villa['villa_code']}*\n"
        f"\n"
        f"🏙 شهر: {villa.get('city', '—')}\n"
        f"🌊 منطقه: {villa.get('area_type', '—')}\n"
        f"🏡 نوع: {_villa_type(villa)}\n"
        f"📄 سند: {villa.get('document_type', '—')}\n"
        f"💰 قیمت: {fmt_price(villa.get('price'))}   {price_category(villa.get('price'))}\n"
        f"\n"
        f"📐 متراژ زمین: {villa.get('land_size', '—')} متر مربع\n"
        f"🏗 متراژ بنا: {villa.get('building_size', '—')} متر مربع\n"
        f"🛏 تعداد اتاق: {villa.get('bedrooms', '—')}\n"
        f"\n"
        f"✨ امکانات:\n{features_block}\n"
        f"\n"
        f"🖼 تصاویر: {len(photos)} عکس  ·  🎥 ویدیو: {has_video}  ·  📍 موقعیت: {has_loc}\n"
        f"\n"
        f"📝 توضیحات:\n{desc}"
    )

    if len(text) > 4000:
        overflow = len(text) - 4000
        desc = desc[: max(0, len(desc) - overflow - 3)] + "..."
        text = (
            f"📋 *مشخصات کامل — ویلا {villa['villa_code']}*\n"
            f"\n"
            f"🏙 شهر: {villa.get('city', '—')}\n"
            f"🌊 منطقه: {villa.get('area_type', '—')}\n"
            f"🏡 نوع: {_villa_type(villa)}\n"
            f"📄 سند: {villa.get('document_type', '—')}\n"
            f"💰 قیمت: {fmt_price(villa.get('price'))}\n"
            f"\n"
            f"📐 متراژ زمین: {villa.get('land_size', '—')} متر مربع\n"
            f"🏗 متراژ بنا: {villa.get('building_size', '—')} متر مربع\n"
            f"🛏 تعداد اتاق: {villa.get('bedrooms', '—')}\n"
            f"\n"
            f"✨ امکانات:\n{features_block}\n"
            f"\n"
            f"🖼 تصاویر: {len(photos)} عکس  ·  🎥 ویدیو: {has_video}  ·  📍 موقعیت: {has_loc}\n"
            f"\n"
            f"📝 توضیحات:\n{desc}"
        )
    return text


def _villa_inline_kb(villa_id: int, idx: int, total: int) -> InlineKeyboardMarkup:
    has_next   = idx + 1 < total
    next_label = f"➡️ بعدی  ({idx + 1}/{total})" if has_next else f"✅ آخرین  ({total}/{total})"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 مشخصات کامل",   callback_data=f"browse_detail_{villa_id}"),
        ],
        [
            InlineKeyboardButton("☎️ درخواست بازدید", callback_data=f"browse_visit_{villa_id}"),
            InlineKeyboardButton(next_label,            callback_data="browse_next"),
        ],
    ])


async def _send_villa_card(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    villa: dict,
    idx: int,
    total: int,
) -> None:
    text   = _villa_card(villa, idx, total)
    kb     = _villa_inline_kb(villa["id"], idx, total)
    photos = _photos_list(villa)

    if photos:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=photos[0],
            caption=text,
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=kb,
        )

# ── Step 1: choose region ──────────────────────────────────────────────────────

async def start_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["browse"] = {}
    await update.message.reply_text(
        "🔍 *جستجوی ویلا*\n\n"
        "منطقه مورد نظر خود را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=BROWSE_AREA_KB,
    )
    return BROWSE_AREA


async def handle_browse_area(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("browse", None)
        await update.message.reply_text(
            "به منوی اصلی بازگشتید.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END

    area_value = AREA_TYPE_MAP.get(text)
    if area_value is None:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=BROWSE_AREA_KB,
        )
        return BROWSE_AREA

    context.user_data["browse"]["area_type"]  = area_value
    context.user_data["browse"]["area_label"] = text

    await update.message.reply_text(
        "💰 بازه قیمتی مورد نظر را انتخاب کنید:",
        reply_markup=BROWSE_BUDGET_KB,
    )
    return BROWSE_BUDGET

# ── Step 2: choose budget → search ────────────────────────────────────────────

async def handle_browse_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        await update.message.reply_text(
            "🔍 *جستجوی ویلا*\n\n"
            "منطقه مورد نظر خود را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=BROWSE_AREA_KB,
        )
        return BROWSE_AREA

    if text not in BUDGET_MAP:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=BROWSE_BUDGET_KB,
        )
        return BROWSE_BUDGET

    min_price, max_price = BUDGET_MAP[text]
    browse = context.user_data.get("browse", {})
    area_type  = browse.get("area_type", "")
    area_label = browse.get("area_label", area_type)

    await update.message.reply_text("🔍 در حال جستجو...", reply_markup=ReplyKeyboardRemove())

    results = search_villas(
        area_type=area_type,
        min_price=min_price,
        max_price=max_price,
    )

    main_kb = get_main_keyboard(update.effective_user.id)

    if not results:
        await update.message.reply_text(
            "😔 *ویلایی با این مشخصات یافت نشد.*\n\n"
            "می‌توانید با بازه قیمتی یا منطقه دیگری جستجو کنید.",
            parse_mode="Markdown",
            reply_markup=main_kb,
        )
        context.user_data.pop("browse", None)
        return ConversationHandler.END

    context.user_data["browse_results"] = results
    context.user_data["browse_idx"]     = 0

    region_name = "ساحلی" if area_type == "ساحلی" else "جنگلی"
    await update.message.reply_text(
        f"✅ *{len(results)} ویلا* در منطقه {region_name} یافت شد:",
        parse_mode="Markdown",
        reply_markup=main_kb,
    )
    await _send_villa_card(update.effective_chat.id, context, results[0], 0, len(results))
    return ConversationHandler.END

# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("browse", None)
    await update.message.reply_text(
        "جستجو لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END

# ── Inline callbacks ───────────────────────────────────────────────────────────

async def cb_browse_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    results = context.user_data.get("browse_results", [])
    idx     = context.user_data.get("browse_idx", 0) + 1

    if not results or idx >= len(results):
        await query.answer("✅ همه ویلاها نمایش داده شدند.", show_alert=True)
        return

    await query.answer()
    context.user_data["browse_idx"] = idx
    await _send_villa_card(query.message.chat_id, context, results[idx], idx, len(results))


async def cb_browse_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.split("_")[-1])
    villa    = get_villa_by_id(villa_id)

    if not villa:
        await query.message.reply_text("⚠️ اطلاعات ویلا یافت نشد.")
        return

    detail_text = _villa_full_detail(villa)
    photos      = _photos_list(villa)

    map_kb = None
    if villa.get("latitude") is not None and villa.get("longitude") is not None:
        maps_url = f"https://www.google.com/maps?q={villa['latitude']},{villa['longitude']}"
        map_kb   = InlineKeyboardMarkup([
            [InlineKeyboardButton("📍 مشاهده روی نقشه", url=maps_url)]
        ])

    if len(photos) > 1:
        media = [InputMediaPhoto(media=p) for p in photos]
        await query.message.reply_media_group(media=media)
        await query.message.reply_text(detail_text, parse_mode="Markdown", reply_markup=map_kb)
    elif len(photos) == 1:
        if len(detail_text) <= 1024:
            await query.message.reply_photo(
                photo=photos[0], caption=detail_text,
                parse_mode="Markdown", reply_markup=map_kb,
            )
        else:
            await query.message.reply_photo(photo=photos[0])
            await query.message.reply_text(detail_text, parse_mode="Markdown", reply_markup=map_kb)
    else:
        await query.message.reply_text(detail_text, parse_mode="Markdown", reply_markup=map_kb)

# ── ConversationHandler factory ────────────────────────────────────────────────

def build_browse_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔍 جستجو ویلا$"), start_browse),
        ],
        states={
            BROWSE_AREA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_browse_area)],
            BROWSE_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_browse_budget)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_browse),
            CommandHandler("start",  cancel_browse),
        ],
    )


def browse_callback_handlers() -> list:
    return [
        CallbackQueryHandler(cb_browse_next,   pattern="^browse_next$"),
        CallbackQueryHandler(cb_browse_detail, pattern="^browse_detail_"),
    ]
