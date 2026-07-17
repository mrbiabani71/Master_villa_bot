from telegram import (
    Update,
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
from database import is_favorite, add_favorite, remove_favorite, is_in_compare, add_compare, remove_compare, get_user_compare

# ── Constants ──────────────────────────────────────────────────────────────────

# index → (internal value, short display label)
AREAS: list[tuple[str, str]] = [
    ("ساحلی", "🏖 ساحلی  (محمودآباد، ایزدشهر، سرخرود)"),
    ("جنگلی", "🌲 جنگلی  (نور، آمل، چمستان)"),
]

BUDGETS: list[tuple[str, float, float | None]] = [
    ("🟢 اقتصادی    (زیر ۷ میلیارد)",         0,              7_000_000_000),
    ("🔵 متوسط      (۷ تا ۱۰ میلیارد)",       7_000_000_000,  10_000_000_000),
    ("🟣 نیمه لوکس  (۱۰ تا ۱۵ میلیارد)",     10_000_000_000, 15_000_000_000),
    ("🔴 لوکس       (بالای ۱۵ میلیارد)",      15_000_000_000, None),
]
BUDGET_LABELS = [b[0] for b in BUDGETS]

# ── Inline keyboard builders ───────────────────────────────────────────────────

def _browse_area_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"browse_area_{i}")]
         for i, (_, label) in enumerate(AREAS)]
        + [[InlineKeyboardButton("🔙 بازگشت", callback_data="browse_area_back")]]
    )

def _browse_budget_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"browse_budget_{i}")]
         for i, label in enumerate(BUDGET_LABELS)]
        + [[InlineKeyboardButton("🔙 بازگشت", callback_data="browse_budget_back")]]
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


def _villa_inline_kb(
    villa_id: int,
    idx: int,
    total: int,
    is_fav: bool = False,
    is_cmp: bool = False,
    cmp_count: int = 0,
) -> InlineKeyboardMarkup:
    has_next   = idx + 1 < total
    next_label = f"➡️ بعدی  ({idx + 1}/{total})" if has_next else f"✅ آخرین  ({total}/{total})"
    fav_label  = "💔 حذف از علاقه‌مندی‌ها" if is_fav else "❤️ افزودن به علاقه‌مندی‌ها"
    fav_data   = f"fav_remove_{villa_id}" if is_fav else f"fav_add_{villa_id}"
    cmp_label  = "✅ حذف از مقایسه" if is_cmp else "⚖️ افزودن برای مقایسه"
    cmp_data   = f"cmp_remove_{villa_id}" if is_cmp else f"cmp_add_{villa_id}"

    rows = [
        [InlineKeyboardButton("📋 مشخصات کامل", callback_data=f"browse_detail_{villa_id}")],
        [InlineKeyboardButton(fav_label, callback_data=fav_data)],
        [InlineKeyboardButton(cmp_label, callback_data=cmp_data)],
    ]

    if cmp_count >= 2:
        rows.append([
            InlineKeyboardButton("📊 نمایش مقایسه", callback_data="cmp_view"),
        ])

    rows.append([
        InlineKeyboardButton("☎️ درخواست بازدید", callback_data=f"browse_visit_{villa_id}"),
        InlineKeyboardButton(next_label,            callback_data="browse_next"),
    ])

    return InlineKeyboardMarkup(rows)


async def _send_villa_card(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    villa: dict,
    idx: int,
    total: int,
    user_id: int = 0,
) -> None:
    text      = _villa_card(villa, idx, total)
    fav       = is_favorite(user_id, villa["id"])   if user_id else False
    cmp       = is_in_compare(user_id, villa["id"]) if user_id else False
    cmp_count = len(get_user_compare(user_id))      if user_id else 0
    kb        = _villa_inline_kb(villa["id"], idx, total, is_fav=fav, is_cmp=cmp, cmp_count=cmp_count)
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
        reply_markup=_browse_area_kb(),
    )
    return BROWSE_AREA


async def handle_browse_area(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "browse_area_back":
        context.user_data.pop("browse", None)
        await query.edit_message_text(
            "به منوی اصلی بازگشتید.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    idx        = int(query.data.split("_")[-1])
    area_value, area_label = AREAS[idx]
    context.user_data.setdefault("browse", {})
    context.user_data["browse"]["area_type"]  = area_value
    context.user_data["browse"]["area_label"] = area_label

    await query.edit_message_text(
        "💰 بازه قیمتی مورد نظر را انتخاب کنید:",
        reply_markup=_browse_budget_kb(),
    )
    return BROWSE_BUDGET

# ── Step 2: choose budget → search ────────────────────────────────────────────

async def handle_browse_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "browse_budget_back":
        await query.edit_message_text(
            "🔍 *جستجوی ویلا*\n\n"
            "منطقه مورد نظر خود را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=_browse_area_kb(),
        )
        return BROWSE_AREA

    idx                    = int(query.data.split("_")[-1])
    label, min_price, max_price = BUDGETS[idx]
    browse     = context.user_data.get("browse", {})
    area_type  = browse.get("area_type", "")

    await query.edit_message_text("🔍 در حال جستجو...")

    results = search_villas(
        area_type=area_type,
        min_price=min_price,
        max_price=max_price,
    )

    if not results:
        await query.edit_message_text(
            "😔 *ویلایی با این مشخصات یافت نشد.*\n\n"
            "می‌توانید با بازه قیمتی یا منطقه دیگری جستجو کنید.",
            parse_mode="Markdown",
        )
        context.user_data.pop("browse", None)
        return ConversationHandler.END

    context.user_data["browse_results"] = results
    context.user_data["browse_idx"]     = 0

    region_name = "ساحلی" if area_type == "ساحلی" else "جنگلی"
    await query.edit_message_text(
        f"✅ *{len(results)} ویلا* در منطقه {region_name} یافت شد:",
        parse_mode="Markdown",
    )
    await _send_villa_card(query.message.chat_id, context, results[0], 0, len(results), query.from_user.id)
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
    await _send_villa_card(query.message.chat_id, context, results[idx], idx, len(results), query.from_user.id)


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
            BROWSE_AREA:   [CallbackQueryHandler(handle_browse_area,   pattern="^browse_area_")],
            BROWSE_BUDGET: [CallbackQueryHandler(handle_browse_budget, pattern="^browse_budget_")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_browse),
            CommandHandler("start",  cancel_browse),
        ],
    )


async def cb_fav_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query    = update.callback_query
    user_id  = query.from_user.id
    data     = query.data
    villa_id = int(data.split("_")[-1])

    if data.startswith("fav_add_"):
        add_favorite(user_id, villa_id)
        is_fav = True
        await query.answer("❤️ اضافه شد به علاقه‌مندی‌ها")
    else:
        remove_favorite(user_id, villa_id)
        is_fav = False
        await query.answer("💔 حذف شد از علاقه‌مندی‌ها")

    results   = context.user_data.get("browse_results", [])
    idx       = context.user_data.get("browse_idx", 0)
    total     = len(results) if results else 1
    is_cmp    = is_in_compare(user_id, villa_id)
    cmp_count = len(get_user_compare(user_id))

    new_kb = _villa_inline_kb(villa_id, idx, total, is_fav=is_fav, is_cmp=is_cmp, cmp_count=cmp_count)
    try:
        await query.edit_message_reply_markup(reply_markup=new_kb)
    except Exception:
        pass


async def cb_cmp_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query    = update.callback_query
    user_id  = query.from_user.id
    data     = query.data
    villa_id = int(data.split("_")[-1])

    if data.startswith("cmp_add_"):
        added = add_compare(user_id, villa_id)
        if added:
            is_cmp = True
            await query.answer("⚖️ اضافه شد به لیست مقایسه")
        else:
            await query.answer(
                "⚠️ حداکثر ۳ ویلا را می‌توانید مقایسه کنید.",
                show_alert=True,
            )
            return
    else:
        remove_compare(user_id, villa_id)
        is_cmp = False
        await query.answer("✅ حذف شد از لیست مقایسه")

    results   = context.user_data.get("browse_results", [])
    idx       = context.user_data.get("browse_idx", 0)
    total     = len(results) if results else 1
    is_fav    = is_favorite(user_id, villa_id)
    cmp_count = len(get_user_compare(user_id))

    new_kb = _villa_inline_kb(villa_id, idx, total, is_fav=is_fav, is_cmp=is_cmp, cmp_count=cmp_count)
    try:
        await query.edit_message_reply_markup(reply_markup=new_kb)
    except Exception:
        pass


def browse_callback_handlers() -> list:
    return [
        CallbackQueryHandler(cb_browse_next,   pattern="^browse_next$"),
        CallbackQueryHandler(cb_browse_detail, pattern="^browse_detail_"),
        CallbackQueryHandler(cb_fav_toggle,    pattern="^fav_add_"),
        CallbackQueryHandler(cb_fav_toggle,    pattern="^fav_remove_"),
        CallbackQueryHandler(cb_cmp_toggle,    pattern="^cmp_add_"),
        CallbackQueryHandler(cb_cmp_toggle,    pattern="^cmp_remove_"),
    ]
