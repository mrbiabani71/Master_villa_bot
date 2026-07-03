from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler

# ── FAQ content ────────────────────────────────────────────────────────────────

# TODO: replace with the real t.me link to the educational post about "سند شورایی"
SHOURAEI_POST_LINK = "https://t.me/master_villa_channel"

FAQ_ITEMS = [
    ("📄 سند ویلا",           "faq_deed"),
    ("👀 بازدید حضوری",       "faq_visit"),
    ("💰 شرایط پرداخت",       "faq_payment"),
    ("🏡 واقعی بودن فایل‌ها", "faq_real"),
    ("📍 مناطق تحت فعالیت",   "faq_areas"),
]

FAQ_ANSWERS = {
    "faq_deed": (
        "📄 *سند ملک*\n\n"
        "پیش از معرفی هر ویلا، اسناد حقوقی آن بررسی می‌شود. "
        "ویلاها ممکن است دارای انواع مختلف سند باشند، از جمله:\n\n"
        "• سند تک‌برگ\n"
        "• سند شش‌دانگ\n"
        "• سند شورایی\n"
        "• سایر مدارک معتبر\n\n"
        "نوع سند هر ویلا همیشه به‌صورت شفاف در مشخصات همان آگهی نمایش داده می‌شود "
        "تا خریداران بتوانند تصمیم آگاهانه‌ای بگیرند.\n\n"
        f"📎 برای آشنایی کامل با سند شورایی، این پست آموزشی را مطالعه کنید:\n{SHOURAEI_POST_LINK}"
    ),
    "faq_visit": (
        "👀 *بازدید حضوری*\n\n"
        "تمام فایل‌هایی که توسط مستر ویلا معرفی می‌شوند، تا زمانی که موجود باشند، "
        "امکان بازدید حضوری دارند.\n\n"
        "فقط برای اینکه وقت شما بی‌دلیل تلف نشود، وضعیت فایل تا یک روز قبل از بازدید "
        "دوباره استعلام می‌شود تا از موجود بودن آن مطمئن شویم.\n\n"
        "هدف ما این است که وقتی برای بازدید می‌آیید، با یک فایل واقعی و آماده معامله روبه‌رو شوید."
    ),
    "faq_payment": (
        "💰 *شرایط پرداخت*\n\n"
        "اگر بودجه شما کمتر از قیمت ملک است، در بسیاری از موارد می‌توانیم "
        "شرایط اقساطی یا پرداخت مرحله‌ای را معرفی کنیم.\n\n"
        "درخواست مشاوره ثبت کنید و ما بهترین گزینه‌های موجود را بررسی خواهیم کرد."
    ),
    "faq_real": (
        "🏡 *واقعی بودن فایل‌ها*\n\n"
        "تمام ویلاهای منتشرشده در مستر ویلا واقعی، قابل بازدید و با اطلاعات "
        "شفاف ارائه شده‌اند.\n\n"
        "ما فایل‌های ساختگی یا قیمت‌های غیرواقعی منتشر نمی‌کنیم."
    ),
    "faq_areas": (
        "📍 *مناطق تحت فعالیت*\n\n"
        "مستر ویلا بر ویلاهای انتخابی در مناطق زیر تمرکز دارد:\n\n"
        "• محمودآباد\n"
        "• سرخرود\n"
        "• ایزدشهر\n"
        "• نور\n"
        "• چمستان\n"
        "• آمل"
    ),
}

# ── Keyboards ──────────────────────────────────────────────────────────────────

def _faq_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data)] for label, data in FAQ_ITEMS]
        + [[InlineKeyboardButton("🔙 بازگشت", callback_data="faq_close")]]
    )


def _faq_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به سوالات", callback_data="faq_menu")]
    ])

# ── Handlers ───────────────────────────────────────────────────────────────────

FAQ_MENU_TEXT = (
    "❓ *سوالات پرتکرار مستر ویلا*\n\n"
    "هر سوالی درباره خرید ویلای شمال داری، احتمالاً جوابش همینجاست 👇"
)


async def show_faq_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called from the main message handler when user taps ❓ سوالات پرتکرار."""
    await update.message.reply_text(
        FAQ_MENU_TEXT,
        parse_mode="Markdown",
        reply_markup=_faq_menu_kb(),
    )


async def cb_faq_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to the FAQ topic list (Back button inside an answer)."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        FAQ_MENU_TEXT,
        parse_mode="Markdown",
        reply_markup=_faq_menu_kb(),
    )


async def cb_faq_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the answer for a specific FAQ topic."""
    query = update.callback_query
    await query.answer()
    answer = FAQ_ANSWERS.get(query.data)
    if not answer:
        return
    await query.edit_message_text(
        answer,
        parse_mode="Markdown",
        reply_markup=_faq_back_kb(),
    )


async def cb_faq_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the FAQ message when user taps 🔙 بازگشت on the main menu."""
    query = update.callback_query
    await query.answer()
    await query.delete_message()

# ── Handler list (add to app in Bot.py) ───────────────────────────────────────

def faq_callback_handlers() -> list:
    return [
        CallbackQueryHandler(cb_faq_menu,   pattern="^faq_menu$"),
        CallbackQueryHandler(cb_faq_close,  pattern="^faq_close$"),
        CallbackQueryHandler(cb_faq_answer, pattern="^faq_"),
    ]
