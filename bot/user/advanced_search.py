"""
Villa search entry point and category (step-by-step filter) search.

Entering "🔍 جستجو ویلا" shows an inline search-type menu on ONE message:
  - 🎯 جستجوی هوشمند   — rule-based natural-language parser; asks for
    missing region/price via follow-up messages when needed.
  - 📋 جستجوی دسته‌بندی — guided step-by-step filter flow.  Every step
    (region → city → price → optional filters) edits the SAME initial
    message via edit_message_text / edit_message_reply_markup.
    No new messages are sent until the first villa card is displayed.

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

BACK = "🔙 بازگشت"   # kept for smart-search text-input back detection

REGION_LABELS = ["🏖 ساحلی", "🌲 جنگلی"]
REGION_VALUES = ["ساحلی", "جنگلی"]
REGION_MAP    = {"🏖 ساحلی": "ساحلی", "🌲 جنگلی": "جنگلی"}

REGION_CITIES: dict[str, list[str]] = {
    "ساحلی": ["محمودآباد", "ایزدشهر", "سرخرود"],
    "جنگلی": ["نور", "آمل", "چمستان"],
}

PRICE_BANDS: list[tuple[str, float, float | None]] = [
    ("💰 ۵ تا ۷ میلیارد",   5_000_000_000,  7_000_000_000),
    ("💰 ۷ تا ۱۰ میلیارد",  7_000_000_000,  10_000_000_000),
    ("💰 ۱۰ تا ۱۵ میلیارد", 10_000_000_000, 15_000_000_000),
    ("💰 بالای ۱۵ میلیارد", 15_000_000_000, None),
]
PRICE_LABELS = [p[0] for p in PRICE_BANDS]
PRICE_MAP    = {p[0]: (p[1], p[2]) for p in PRICE_BANDS}

BEDROOM_OPTIONS        = [None, 2, 3, 4]
MASTER_BEDROOM_OPTIONS = [None, 1, 2, 3]
DOCUMENT_OPTIONS       = [None, "tak_barg", "parvaneh"]
DOCUMENT_LABELS        = {None: "هر نوع", "tak_barg": "سند تک برگ", "parvaneh": "پروانه ساخت"}

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

# ── Inline keyboard builders ───────────────────────────────────────────────────

def _search_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 جستجوی هوشمند",    callback_data="smenu_smart")],
        [InlineKeyboardButton("📋 جستجوی دسته‌بندی", callback_data="smenu_cat")],
        [InlineKeyboardButton("🔙 بازگشت",            callback_data="smenu_back")],
    ])


def _region_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"adv_r_{i}")]
         for i, label in enumerate(REGION_LABELS)]
        + [[InlineKeyboardButton("🔙 بازگشت", callback_data="adv_r_back")]]
    )


def _city_kb(region: str) -> InlineKeyboardMarkup:
    cities = REGION_CITIES.get(region, [])
    rows = [[InlineKeyboardButton(c, callback_data=f"adv_c_{i}")]
            for i, c in enumerate(cities)]
    rows.append([InlineKeyboardButton("🏙 همه شهرهای این منطقه", callback_data="adv_c_all")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adv_c_back")])
    return InlineKeyboardMarkup(rows)


def _price_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"adv_p_{i}")]
         for i, label in enumerate(PRICE_LABELS)]
        + [[InlineKeyboardButton("🔙 بازگشت", callback_data="adv_p_back")]]
    )


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

# ── Step 0: search-type menu ───────────────────────────────────────────────────

async def start_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — sends the ONE message that the category path will reuse."""
    await update.message.reply_text(
        "🔍 *جستجوی ویلا*\n\n"
        "روش جستجو را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_search_menu_kb(),
    )
    return SEARCH_MENU


async def handle_search_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "smenu_back":
        await query.edit_message_text("به منوی اصلی بازگشتید.")
        return ConversationHandler.END

    if query.data == "smenu_smart":
        context.user_data["smart"] = {}
        await query.edit_message_text(
            "🎯 *جستجوی هوشمند*\n\n"
            "متن جستجوی خود را به فارسی بنویسید، مثلاً:\n"
            "«ویلای جنگلی چمستان تا ۱۲ میلیارد با استخر»\n"
            "«ویلا ساحلی محمودآباد ۳ خواب»",
            parse_mode="Markdown",
        )
        return SMART_TEXT

    # smenu_cat — start category flow, reuse this same message
    context.user_data["adv"] = {}
    context.user_data["adv_filters"] = dict(DEFAULT_FILTERS)
    await query.edit_message_text(
        "📋 *جستجوی دسته‌بندی ویلا*\n\n"
        "۱️⃣ ابتدا نوع منطقه را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_region_kb(),
    )
    return ADV_REGION

# ── Step 1: region ─────────────────────────────────────────────────────────────

async def handle_adv_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "adv_r_back":
        await query.edit_message_text(
            "🔍 *جستجوی ویلا*\n\n"
            "روش جستجو را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=_search_menu_kb(),
        )
        return SEARCH_MENU

    idx    = int(query.data.split("_")[-1])
    region = REGION_VALUES[idx]
    context.user_data.setdefault("adv", {})["region"] = region

    await query.edit_message_text(
        "📋 *جستجوی دسته‌بندی ویلا*\n\n"
        "۲️⃣ شهر مورد نظر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_city_kb(region),
    )
    return ADV_CITY

# ── Step 2: city ───────────────────────────────────────────────────────────────

async def handle_adv_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query  = update.callback_query
    await query.answer()
    region = context.user_data.get("adv", {}).get("region", "")

    if query.data == "adv_c_back":
        await query.edit_message_text(
            "📋 *جستجوی دسته‌بندی ویلا*\n\n"
            "۱️⃣ ابتدا نوع منطقه را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=_region_kb(),
        )
        return ADV_REGION

    if query.data == "adv_c_all":
        context.user_data["adv"]["city"] = None
    else:
        idx    = int(query.data.split("_")[-1])
        cities = REGION_CITIES.get(region, [])
        context.user_data["adv"]["city"] = cities[idx]

    await query.edit_message_text(
        "📋 *جستجوی دسته‌بندی ویلا*\n\n"
        "۳️⃣ بازه قیمتی مورد نظر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_price_kb(),
    )
    return ADV_PRICE

# ── Step 3: price → filters ────────────────────────────────────────────────────

async def handle_adv_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query  = update.callback_query
    await query.answer()
    region = context.user_data.get("adv", {}).get("region", "")

    if query.data == "adv_p_back":
        await query.edit_message_text(
            "📋 *جستجوی دسته‌بندی ویلا*\n\n"
            "۲️⃣ شهر مورد نظر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=_city_kb(region),
        )
        return ADV_CITY

    idx                      = int(query.data.split("_")[-1])
    label, min_price, max_price = PRICE_BANDS[idx]
    context.user_data["adv"]["price_label"] = label
    context.user_data["adv"]["min_price"]   = min_price
    context.user_data["adv"]["max_price"]   = max_price

    f = context.user_data.setdefault("adv_filters", dict(DEFAULT_FILTERS))
    await query.edit_message_text(
        _filters_text(f),
        parse_mode="Markdown",
        reply_markup=_filters_kb(),
    )
    return ADV_FILTERS

# ── Step 4: optional filters (inline) → search ────────────────────────────────

async def _run_search(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Execute the search and post results. Sends new messages only at this point."""
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
    f    = context.user_data.setdefault("adv_filters", dict(DEFAULT_FILTERS))

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
        # Edit back to the price step — still the same single message
        await query.edit_message_text(
            "📋 *جستجوی دسته‌بندی ویلا*\n\n"
            "۳️⃣ بازه قیمتی مورد نظر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=_price_kb(),
        )
        return ADV_PRICE
    elif data == "advf_search":
        # Remove buttons from the search-menu message, then post results below it
        await query.edit_message_text("🔍 در حال جستجو...")
        await _run_search(context, query.message.chat_id)
        context.user_data.pop("adv", None)
        context.user_data.pop("adv_filters", None)
        return ConversationHandler.END

    await query.edit_message_text(_filters_text(f), parse_mode="Markdown", reply_markup=_filters_kb())
    return ADV_FILTERS

# ── Smart search (text-based — separate from category path) ───────────────────

def _smart_to_adv(parsed: dict) -> tuple[dict, dict]:
    adv = {
        "region":    parsed.get("region"),
        "city":      parsed.get("city"),
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
    context.user_data["adv"]         = adv
    context.user_data["adv_filters"] = f

    await update.message.reply_text("🔍 در حال جستجو...")
    await _run_search(context, update.effective_chat.id)

    context.user_data.pop("adv",         None)
    context.user_data.pop("adv_filters", None)
    context.user_data.pop("smart",       None)
    return ConversationHandler.END


async def handle_smart_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("smart", None)
        await update.message.reply_text(
            "🔍 *جستجوی ویلا*\n\n"
            "روش جستجو را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=_search_menu_kb(),
        )
        return SEARCH_MENU

    parsed = parse_smart_query(text)
    context.user_data["smart"] = parsed

    if parsed.get("region") is None:
        await update.message.reply_text(
            "متوجه منطقه مورد نظر نشدم 🙏\n"
            "لطفاً نوع منطقه را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(label, callback_data=f"smart_r_{i}")]
                for i, label in enumerate(REGION_LABELS)
            ]),
        )
        return SMART_ASK_REGION

    if parsed.get("min_price") is None and parsed.get("max_price") is None:
        await update.message.reply_text(
            "متوجه بازه قیمتی نشدم 🙏\n"
            "لطفاً محدوده قیمت را بنویسید، مثلاً: «تا ۱۰ میلیارد» یا «بین ۷ تا ۱۲ میلیارد»",
        )
        return SMART_ASK_PRICE

    return await _finish_smart_search(update, context)


async def handle_smart_ask_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the inline region button tapped after a smart query without a region."""
    query = update.callback_query
    await query.answer()

    idx    = int(query.data.split("_")[-1])
    region = REGION_VALUES[idx]
    parsed = context.user_data.setdefault("smart", {})
    parsed["region"] = region

    if parsed.get("min_price") is None and parsed.get("max_price") is None:
        await query.edit_message_text(
            "متوجه بازه قیمتی نشدم 🙏\n"
            "لطفاً محدوده قیمت را بنویسید، مثلاً: «تا ۱۰ میلیارد» یا «بین ۷ تا ۱۲ میلیارد»",
        )
        return SMART_ASK_PRICE

    # Both region and price are now known — run search
    adv, f = _smart_to_adv(parsed)
    context.user_data["adv"]         = adv
    context.user_data["adv_filters"] = f
    await query.edit_message_text("🔍 در حال جستجو...")
    await _run_search(context, query.message.chat_id)
    context.user_data.pop("adv",         None)
    context.user_data.pop("adv_filters", None)
    context.user_data.pop("smart",       None)
    return ConversationHandler.END


async def handle_smart_ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("smart", None)
        await update.message.reply_text(
            "🔍 *جستجوی ویلا*\n\n"
            "روش جستجو را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=_search_menu_kb(),
        )
        return SEARCH_MENU

    parsed_extra = parse_smart_query(text)
    min_price    = parsed_extra.get("min_price")
    max_price    = parsed_extra.get("max_price")

    if min_price is None and max_price is None:
        await update.message.reply_text(
            "متوجه نشدم 🙏 لطفاً محدوده قیمت را بنویسید، "
            "مثلاً: «تا ۱۰ میلیارد» یا «بین ۷ تا ۱۲ میلیارد»",
        )
        return SMART_ASK_PRICE

    parsed = context.user_data.setdefault("smart", {})
    parsed["min_price"] = min_price
    parsed["max_price"] = max_price

    return await _finish_smart_search(update, context)

# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel_advanced_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("adv",         None)
    context.user_data.pop("adv_filters", None)
    context.user_data.pop("smart",       None)
    await update.message.reply_text(
        "جستجو لغو شد.",
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
            SEARCH_MENU: [
                CallbackQueryHandler(handle_search_menu_cb, pattern="^smenu_"),
            ],
            SMART_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_smart_text),
            ],
            SMART_ASK_REGION: [
                CallbackQueryHandler(handle_smart_ask_region, pattern="^smart_r_"),
            ],
            SMART_ASK_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_smart_ask_price),
            ],
            ADV_REGION: [
                CallbackQueryHandler(handle_adv_region, pattern="^adv_r_"),
            ],
            ADV_CITY: [
                CallbackQueryHandler(handle_adv_city, pattern="^adv_c_"),
            ],
            ADV_PRICE: [
                CallbackQueryHandler(handle_adv_price, pattern="^adv_p_"),
            ],
            ADV_FILTERS: [
                CallbackQueryHandler(cb_adv_filters, pattern="^advf_"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_advanced_search),
            CommandHandler("start",  cancel_advanced_search),
        ],
        per_message=False,
    )
