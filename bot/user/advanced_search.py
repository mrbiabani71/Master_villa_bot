"""
Guided advanced villa search.

Flow: region → city → price range → optional filters (bedrooms, master
bedrooms, pool, jacuzzi, roof garden, parking, document status, gated
community) → results.

Results are rendered with the exact same villa-card renderer used by the
basic search (photos, villa code, city, price, main details, and a
consultation/visit-request button), and pagination ("next villa" / "full
details" / "request a visit") is handled by the already-registered global
callback handlers in ``user.browse`` — this flow only needs to populate
``context.user_data["browse_results"]`` / ``["browse_idx"]`` the same way
``user.browse`` does, so no changes to browse.py, visit.py, or the channel
importer are required.
"""
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

from pg_villas import advanced_search_villas
from keyboards import get_main_keyboard
from states import ADV_REGION, ADV_CITY, ADV_PRICE, ADV_FILTERS
from user.browse import _send_villa_card

# ── Constants ──────────────────────────────────────────────────────────────────

BACK = "🔙 بازگشت"
ALL_CITIES = "🏙 همه شهرهای این منطقه"

REGION_LABELS = ["🏖 ساحلی", "🌲 جنگلی"]
REGION_MAP = {"🏖 ساحلی": "ساحلی", "🌲 جنگلی": "جنگلی"}

REGION_CITIES: dict[str, list[str]] = {
    "ساحلی": ["محمودآباد", "ایزدشهر", "سرخرود"],
    "جنگلی": ["نور", "آمل", "چمستان"],
}

PRICE_BANDS: list[tuple[str, float, float | None]] = [
    ("💰 ۵ تا ۷ میلیارد",   5_000_000_000, 7_000_000_000),
    ("💰 ۷ تا ۱۰ میلیارد",  7_000_000_000, 10_000_000_000),
    ("💰 ۱۰ تا ۱۵ میلیارد", 10_000_000_000, 15_000_000_000),
    ("💰 بالای ۱۵ میلیارد", 15_000_000_000, None),
]
PRICE_LABELS = [p[0] for p in PRICE_BANDS]
PRICE_MAP    = {p[0]: (p[1], p[2]) for p in PRICE_BANDS}

BEDROOM_OPTIONS       = [None, 2, 3, 4]
MASTER_BEDROOM_OPTIONS = [None, 1, 2, 3]
DOCUMENT_OPTIONS      = [None, "tak_barg", "parvaneh"]
DOCUMENT_LABELS       = {None: "هر نوع", "tak_barg": "سند تک برگ", "parvaneh": "پروانه ساخت"}

DEFAULT_FILTERS = {
    "bedrooms": None,
    "master_bedrooms": None,
    "pool": False,
    "jacuzzi": False,
    "roof_garden": False,
    "parking": False,
    "gated": False,
    "document": None,
}

# ── Keyboards ──────────────────────────────────────────────────────────────────

REGION_KB = ReplyKeyboardMarkup([[label] for label in REGION_LABELS] + [[BACK]], resize_keyboard=True)
PRICE_KB  = ReplyKeyboardMarkup([[label] for label in PRICE_LABELS] + [[BACK]], resize_keyboard=True)


def _city_kb(region: str) -> ReplyKeyboardMarkup:
    cities = REGION_CITIES.get(region, [])
    rows = [[c] for c in cities] + [[ALL_CITIES], [BACK]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def _cycle(options: list, current) -> object:
    idx = options.index(current) if current in options else 0
    return options[(idx + 1) % len(options)]


def _filters_text(f: dict) -> str:
    def mark(v: bool) -> str:
        return "✅" if v else "⬜"

    bedrooms_str        = "هر تعداد" if f["bedrooms"] is None else f"{f['bedrooms']}+"
    master_bedrooms_str = "هر تعداد" if f["master_bedrooms"] is None else f"{f['master_bedrooms']}+"

    return (
        "🎛 *فیلترهای اختیاری*\n\n"
        "این فیلترها اختیاری هستند — می‌توانید هرکدام را روشن/خاموش کنید "
        "یا مستقیم روی «مشاهده نتایج» بزنید.\n\n"
        f"🛏 حداقل تعداد خواب: {bedrooms_str}\n"
        f"🛌 حداقل مستر خواب: {master_bedrooms_str}\n"
        f"{mark(f['pool'])} 🏊 استخر\n"
        f"{mark(f['jacuzzi'])} 🛁 جکوزی\n"
        f"{mark(f['roof_garden'])} 🌿 روف گاردن\n"
        f"{mark(f['parking'])} 🚗 پارکینگ\n"
        f"{mark(f['gated'])} 🏘 داخل شهرک (نگهبانی / حصار)\n"
        f"📄 وضعیت سند: {DOCUMENT_LABELS[f['document']]}\n"
    )


def _filters_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛏 اتاق خواب", callback_data="advf_bed"),
            InlineKeyboardButton("🛌 مستر خواب", callback_data="advf_mbed"),
        ],
        [
            InlineKeyboardButton("🏊 استخر",  callback_data="advf_toggle_pool"),
            InlineKeyboardButton("🛁 جکوزی",  callback_data="advf_toggle_jacuzzi"),
        ],
        [
            InlineKeyboardButton("🌿 روف گاردن", callback_data="advf_toggle_roof_garden"),
            InlineKeyboardButton("🚗 پارکینگ",   callback_data="advf_toggle_parking"),
        ],
        [
            InlineKeyboardButton("🏘 داخل شهرک", callback_data="advf_toggle_gated"),
            InlineKeyboardButton("📄 وضعیت سند", callback_data="advf_doc"),
        ],
        [InlineKeyboardButton("🔄 پاک کردن فیلترها", callback_data="advf_reset")],
        [InlineKeyboardButton("🔙 بازگشت به بازه قیمت", callback_data="advf_back")],
        [InlineKeyboardButton("🔍 مشاهده نتایج",         callback_data="advf_search")],
    ])

# ── Step 1: region ─────────────────────────────────────────────────────────────

async def start_advanced_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["adv"] = {}
    context.user_data["adv_filters"] = dict(DEFAULT_FILTERS)
    await update.message.reply_text(
        "🎯 *جستجوی پیشرفته ویلا*\n\n"
        "۱️⃣ ابتدا نوع منطقه را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=REGION_KB,
    )
    return ADV_REGION


async def handle_adv_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("adv", None)
        context.user_data.pop("adv_filters", None)
        await update.message.reply_text(
            "به منوی اصلی بازگشتید.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END

    region = REGION_MAP.get(text)
    if region is None:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=REGION_KB,
        )
        return ADV_REGION

    context.user_data["adv"]["region"] = region
    await update.message.reply_text(
        "۲️⃣ شهر مورد نظر را انتخاب کنید:",
        reply_markup=_city_kb(region),
    )
    return ADV_CITY

# ── Step 2: city ───────────────────────────────────────────────────────────────

async def handle_adv_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text   = update.message.text.strip()
    region = context.user_data.get("adv", {}).get("region", "")

    if text == BACK:
        await update.message.reply_text(
            "۱️⃣ نوع منطقه را انتخاب کنید:",
            reply_markup=REGION_KB,
        )
        return ADV_REGION

    if text == ALL_CITIES:
        context.user_data["adv"]["city"] = None
    elif text in REGION_CITIES.get(region, []):
        context.user_data["adv"]["city"] = text
    else:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=_city_kb(region),
        )
        return ADV_CITY

    await update.message.reply_text(
        "۳️⃣ بازه قیمتی مورد نظر را انتخاب کنید:",
        reply_markup=PRICE_KB,
    )
    return ADV_PRICE

# ── Step 3: price → optional filters screen ───────────────────────────────────

async def handle_adv_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text   = update.message.text.strip()
    region = context.user_data.get("adv", {}).get("region", "")

    if text == BACK:
        await update.message.reply_text(
            "۲️⃣ شهر مورد نظر را انتخاب کنید:",
            reply_markup=_city_kb(region),
        )
        return ADV_CITY

    if text not in PRICE_MAP:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=PRICE_KB,
        )
        return ADV_PRICE

    min_price, max_price = PRICE_MAP[text]
    context.user_data["adv"]["price_label"] = text
    context.user_data["adv"]["min_price"]   = min_price
    context.user_data["adv"]["max_price"]   = max_price

    await update.message.reply_text("۴️⃣ فیلترهای اختیاری را تنظیم کنید 👇", reply_markup=ReplyKeyboardRemove())
    f = context.user_data.setdefault("adv_filters", dict(DEFAULT_FILTERS))
    await update.message.reply_text(_filters_text(f), parse_mode="Markdown", reply_markup=_filters_kb())
    return ADV_FILTERS

# ── Step 4: optional filters (inline) → search ────────────────────────────────

async def _run_search(update_message_target, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    adv = context.user_data.get("adv", {})
    f   = context.user_data.get("adv_filters", dict(DEFAULT_FILTERS))

    results = advanced_search_villas(
        area_type=adv.get("region", ""),
        min_price=adv.get("min_price", 0),
        max_price=adv.get("max_price"),
        city=adv.get("city"),
        bedrooms=f["bedrooms"],
        master_bedrooms=f["master_bedrooms"],
        has_pool=f["pool"],
        has_jacuzzi=f["jacuzzi"],
        has_roof_garden=f["roof_garden"],
        has_parking=f["parking"],
        gated_community=f["gated"],
        document=f["document"],
    )

    if not results:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "😔 *ویلایی با این مشخصات یافت نشد.*\n\n"
                "می‌توانید فیلترها یا بازه قیمتی را تغییر دهید و دوباره جستجو کنید."
            ),
            parse_mode="Markdown",
        )
        return

    context.user_data["browse_results"] = results
    context.user_data["browse_idx"]     = 0

    region_name = adv.get("region", "—")
    city_name   = adv.get("city") or "همه شهرها"
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ *{len(results)} ویلا* در منطقه {region_name} ({city_name}) یافت شد:",
        parse_mode="Markdown",
    )
    await _send_villa_card(chat_id, context, results[0], 0, len(results))


async def cb_adv_filters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    f = context.user_data.setdefault("adv_filters", dict(DEFAULT_FILTERS))

    if data == "advf_bed":
        f["bedrooms"] = _cycle(BEDROOM_OPTIONS, f["bedrooms"])
    elif data == "advf_mbed":
        f["master_bedrooms"] = _cycle(MASTER_BEDROOM_OPTIONS, f["master_bedrooms"])
    elif data == "advf_toggle_pool":
        f["pool"] = not f["pool"]
    elif data == "advf_toggle_jacuzzi":
        f["jacuzzi"] = not f["jacuzzi"]
    elif data == "advf_toggle_roof_garden":
        f["roof_garden"] = not f["roof_garden"]
    elif data == "advf_toggle_parking":
        f["parking"] = not f["parking"]
    elif data == "advf_toggle_gated":
        f["gated"] = not f["gated"]
    elif data == "advf_doc":
        f["document"] = _cycle(DOCUMENT_OPTIONS, f["document"])
    elif data == "advf_reset":
        context.user_data["adv_filters"] = dict(DEFAULT_FILTERS)
        f = context.user_data["adv_filters"]
    elif data == "advf_back":
        region = context.user_data.get("adv", {}).get("region", "")
        await query.message.reply_text(
            "۲️⃣ شهر مورد نظر را انتخاب کنید:",
            reply_markup=_city_kb(region),
        )
        return ADV_CITY
    elif data == "advf_search":
        await query.edit_message_reply_markup(reply_markup=None)
        await _run_search(query.message, context, query.message.chat_id)
        context.user_data.pop("adv", None)
        context.user_data.pop("adv_filters", None)
        return ConversationHandler.END

    await query.edit_message_text(_filters_text(f), parse_mode="Markdown", reply_markup=_filters_kb())
    return ADV_FILTERS

# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel_advanced_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("adv", None)
    context.user_data.pop("adv_filters", None)
    await update.message.reply_text(
        "جستجوی پیشرفته لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END

# ── ConversationHandler factory ────────────────────────────────────────────────

def build_advanced_search_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎯 جستجوی پیشرفته$"), start_advanced_search),
        ],
        states={
            ADV_REGION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_adv_region)],
            ADV_CITY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_adv_city)],
            ADV_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_adv_price)],
            ADV_FILTERS: [CallbackQueryHandler(cb_adv_filters, pattern="^advf_")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_advanced_search),
            CommandHandler("start",  cancel_advanced_search),
        ],
        per_message=False,
    )
