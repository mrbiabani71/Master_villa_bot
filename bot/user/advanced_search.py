"""
Villa search entry point and category (step-by-step filter) search.

Entering "🔍 جستجو ویلا" first shows a search-type menu with two options:
  - 🎯 جستجوی هوشمند   — placeholder for a future AI/NLP smart search;
    no AI/NLP is implemented yet, it just explains the feature is coming.
  - 📋 جستجوی دسته‌بندی — the existing guided step-by-step filter flow
    (unchanged): region → city → price range → optional filters (bedrooms,
    master bedrooms, pool, jacuzzi, roof garden, parking, document status,
    gated community) → results.

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
from states import (
    SEARCH_MENU,
    ADV_REGION, ADV_CITY, ADV_PRICE, ADV_FILTERS,
    SMART_TEXT, SMART_ASK_REGION, SMART_ASK_PRICE,
)
from user.browse import _send_villa_card
from user.smart_search import parse_smart_query

# ── Constants ──────────────────────────────────────────────────────────────────

BACK = "🔙 بازگشت"
ALL_CITIES = "🏙 همه شهرهای این منطقه"

SMART_SEARCH_LABEL    = "🎯 جستجوی هوشمند"
CATEGORY_SEARCH_LABEL = "📋 جستجوی دسته‌بندی"

SEARCH_MENU_KB = ReplyKeyboardMarkup(
    [[SMART_SEARCH_LABEL], [CATEGORY_SEARCH_LABEL], [BACK]],
    resize_keyboard=True,
)

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

# ── Step 0: search menu (smart vs category) ────────────────────────────────────

async def start_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔍 *جستجوی ویلا*\n\n"
        "روش جستجو را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=SEARCH_MENU_KB,
    )
    return SEARCH_MENU


async def handle_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        await update.message.reply_text(
            "به منوی اصلی بازگشتید.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END

    if text == SMART_SEARCH_LABEL:
        context.user_data["smart"] = {}
        await update.message.reply_text(
            "🎯 *جستجوی هوشمند*\n\n"
            "متن جستجوی خود را به فارسی بنویسید، مثلاً:\n"
            "«ویلای جنگلی چمستان تا ۱۲ میلیارد با استخر»\n"
            "«ویلا ساحلی محمودآباد ۳ خواب»",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([[BACK]], resize_keyboard=True),
        )
        return SMART_TEXT

    if text == CATEGORY_SEARCH_LABEL:
        return await start_category_search(update, context)

    await update.message.reply_text(
        "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
        reply_markup=SEARCH_MENU_KB,
    )
    return SEARCH_MENU

# ── Step 1: region ─────────────────────────────────────────────────────────────

async def start_category_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["adv"] = {}
    context.user_data["adv_filters"] = dict(DEFAULT_FILTERS)
    await update.message.reply_text(
        "📋 *جستجوی دسته‌بندی ویلا*\n\n"
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
            "روش جستجو را انتخاب کنید:",
            reply_markup=SEARCH_MENU_KB,
        )
        return SEARCH_MENU

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

# ── Smart search (Version 1: rule-based parser, no AI/NLP) ─────────────────────
#
# The parsed filters are mapped onto the exact same context.user_data["adv"] /
# ["adv_filters"] shape used by the category search above, then handed to the
# same _run_search() — so both search paths execute identical, unmodified
# search logic. Only region and price are treated as required; if either is
# missing after parsing, we ask ONLY for that one field (no restart of the
# whole guided flow) and merge the answer into the already-parsed filters.

_SMART_ASK_REGION_KB = REGION_KB
_SMART_ASK_PRICE_KB  = ReplyKeyboardMarkup([[BACK]], resize_keyboard=True)


def _smart_to_adv(parsed: dict) -> tuple[dict, dict]:
    adv = {
        "region": parsed.get("region"),
        "city": parsed.get("city"),
        "min_price": parsed.get("min_price") or 0,
        "max_price": parsed.get("max_price"),
    }
    f = dict(DEFAULT_FILTERS)
    f["bedrooms"]        = parsed.get("bedrooms")
    f["master_bedrooms"] = parsed.get("master_bedrooms")
    f["pool"]            = bool(parsed.get("pool"))
    f["jacuzzi"]         = bool(parsed.get("jacuzzi"))
    f["roof_garden"]     = bool(parsed.get("roof_garden"))
    f["parking"]         = bool(parsed.get("parking"))
    f["gated"]           = bool(parsed.get("gated"))
    f["document"]        = parsed.get("document")
    return adv, f


async def _finish_smart_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parsed = context.user_data.get("smart", {})
    adv, f = _smart_to_adv(parsed)
    context.user_data["adv"] = adv
    context.user_data["adv_filters"] = f

    await update.message.reply_text(
        "🔍 در حال جستجو...",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    await _run_search(update.message, context, update.effective_chat.id)

    context.user_data.pop("adv", None)
    context.user_data.pop("adv_filters", None)
    context.user_data.pop("smart", None)
    return ConversationHandler.END


async def handle_smart_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("smart", None)
        await update.message.reply_text(
            "روش جستجو را انتخاب کنید:",
            reply_markup=SEARCH_MENU_KB,
        )
        return SEARCH_MENU

    parsed = parse_smart_query(text)
    context.user_data["smart"] = parsed

    if parsed.get("region") is None:
        await update.message.reply_text(
            "متوجه منطقه مورد نظر نشدم 🙏\n"
            "لطفاً نوع منطقه را انتخاب کنید:",
            reply_markup=_SMART_ASK_REGION_KB,
        )
        return SMART_ASK_REGION

    if parsed.get("min_price") is None and parsed.get("max_price") is None:
        await update.message.reply_text(
            "متوجه بازه قیمتی نشدم 🙏\n"
            "لطفاً محدوده قیمت را بنویسید، مثلاً: «تا ۱۰ میلیارد» یا «بین ۷ تا ۱۲ میلیارد»",
            reply_markup=_SMART_ASK_PRICE_KB,
        )
        return SMART_ASK_PRICE

    return await _finish_smart_search(update, context)


async def handle_smart_ask_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("smart", None)
        await update.message.reply_text(
            "روش جستجو را انتخاب کنید:",
            reply_markup=SEARCH_MENU_KB,
        )
        return SEARCH_MENU

    region = REGION_MAP.get(text)
    if region is None:
        region = parse_smart_query(text).get("region")

    if region is None:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=_SMART_ASK_REGION_KB,
        )
        return SMART_ASK_REGION

    parsed = context.user_data.setdefault("smart", {})
    parsed["region"] = region

    if parsed.get("min_price") is None and parsed.get("max_price") is None:
        await update.message.reply_text(
            "متوجه بازه قیمتی نشدم 🙏\n"
            "لطفاً محدوده قیمت را بنویسید، مثلاً: «تا ۱۰ میلیارد» یا «بین ۷ تا ۱۲ میلیارد»",
            reply_markup=_SMART_ASK_PRICE_KB,
        )
        return SMART_ASK_PRICE

    return await _finish_smart_search(update, context)


async def handle_smart_ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("smart", None)
        await update.message.reply_text(
            "روش جستجو را انتخاب کنید:",
            reply_markup=SEARCH_MENU_KB,
        )
        return SEARCH_MENU

    parsed_extra = parse_smart_query(text)
    min_price, max_price = parsed_extra.get("min_price"), parsed_extra.get("max_price")

    if min_price is None and max_price is None:
        await update.message.reply_text(
            "متوجه نشدم 🙏 لطفاً محدوده قیمت را بنویسید، مثلاً: «تا ۱۰ میلیارد» یا «بین ۷ تا ۱۲ میلیارد»",
            reply_markup=_SMART_ASK_PRICE_KB,
        )
        return SMART_ASK_PRICE

    parsed = context.user_data.setdefault("smart", {})
    parsed["min_price"] = min_price
    parsed["max_price"] = max_price

    return await _finish_smart_search(update, context)


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
        "جستجوی دسته‌بندی لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END

# ── ConversationHandler factory ────────────────────────────────────────────────

def build_advanced_search_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔍 جستجو ویلا$"), start_search_menu),
        ],
        states={
            SEARCH_MENU:     [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_menu)],
            SMART_TEXT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_smart_text)],
            SMART_ASK_REGION:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_smart_ask_region)],
            SMART_ASK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_smart_ask_price)],
            ADV_REGION:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_adv_region)],
            ADV_CITY:        [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_adv_city)],
            ADV_PRICE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_adv_price)],
            ADV_FILTERS:     [CallbackQueryHandler(cb_adv_filters, pattern="^advf_")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_advanced_search),
            CommandHandler("start",  cancel_advanced_search),
        ],
        per_message=False,
    )
