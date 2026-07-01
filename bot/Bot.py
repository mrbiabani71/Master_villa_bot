import warnings
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=Warning)

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN
from keyboards import get_main_keyboard
from database import init_db
from admin.panel import ADMIN_PANEL_BUTTONS, handle_admin_panel, handle_admin_buttons
from admin.add_villa import build_add_villa_conv
from admin.requests import cb_req_page, cb_req_contact, cb_req_delete
from user.browse import build_browse_conv, browse_callback_handlers
from user.visit import build_visit_conv, visit_callback_handlers
from user.consultation import build_consultation_conv
from user.faq import show_faq_menu, faq_callback_handlers
from channel_importer import channel_import_handler

FAQ_TEXT = (
    "❓ *سوالات پرتکرار*\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "📄 *سند ملک چه نوعی است؟*\n"
    "اکثر ویلاهای ما دارای سند تک‌برگ یا سند منگوله‌دار هستند. "
    "اطلاعات دقیق سند در مشخصات هر ویلا درج شده است.\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "🏡 *آیا بازدید حضوری امکان‌پذیر است؟*\n"
    "بله. پس از ثبت درخواست بازدید، مشاوران ما با شما تماس گرفته "
    "و بازدید را هماهنگ می‌کنند. بازدید کاملاً رایگان است.\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "💳 *روش پرداخت و اطمینان از معامله؟*\n"
    "تمام معاملات با حضور کارشناس حقوقی و در دفتر اسناد رسمی انجام "
    "می‌شود. امنیت معامله شما برای ما اولویت اول است.\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "📍 *ویلاها در چه مناطقی هستند؟*\n"
    "ویلاهای ما در مناطق ساحلی (محمودآباد، ایزدشهر، سرخرود) و "
    "جنگلی (نور، آمل، چمستان) واقع شده‌اند.\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "📞 *برای سوالات بیشتر چه کنم؟*\n"
    "از گزینه «📩 درخواست مشاوره» در منوی اصلی استفاده کنید. "
    "مشاوران ما در اسرع وقت با شما تماس می‌گیرند."
)

ABOUT_TEXT = (
    "ℹ️ *درباره ماستر ویلا*\n\n"
    "ماستر ویلا یک مجموعه تخصصی در حوزه خرید و فروش ویلاهای شمال ایران است.\n\n"
    "🎯 *تخصص ما:*\n"
    "ویلاهای ساحلی و جنگلی در بهترین مناطق استان مازندران\n\n"
    "✅ *چرا ماستر ویلا؟*\n"
    "• بیش از ۱۰ سال سابقه در بازار مسکن شمال\n"
    "• ویلاهای تأییدشده با اسناد معتبر\n"
    "• مشاوره رایگان و بازدید بدون هزینه\n"
    "• همراهی کامل تا لحظه انتقال سند\n"
    "• قیمت‌های شفاف و بدون واسطه\n\n"
    "📍 *مناطق فعالیت:*\n"
    "محمودآباد • ایزدشهر • سرخرود • نور • آمل • چمستان\n\n"
    "📞 برای مشاوره رایگان از منوی اصلی اقدام کنید 👇"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋 به ربات *Master Villa* خوش اومدی\n"
        "برای جستجوی ویلا یا درخواست مشاوره از منو استفاده کن:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "❓ سوالات پرتکرار":
        await show_faq_menu(update, context)

    elif text == "ℹ️ درباره ما":
        await update.message.reply_text(ABOUT_TEXT, parse_mode="Markdown")

    elif text == "👑 پنل مدیریت":
        await handle_admin_panel(update, context)

    elif text in ADMIN_PANEL_BUTTONS:
        await handle_admin_buttons(update, context)

    else:
        await update.message.reply_text(
            "لطفاً از منو استفاده کن 👇",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )


init_db()

app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# ── ConversationHandlers (order matters) ───────────────────────────────────────
app.add_handler(build_add_villa_conv())
app.add_handler(build_consultation_conv())
app.add_handler(build_visit_conv())   # must precede browse callbacks (intercepts browse_visit_)
app.add_handler(build_browse_conv())

# ── Inline callbacks: FAQ ─────────────────────────────────────────────────────
for handler in faq_callback_handlers():
    app.add_handler(handler)

# ── Inline callbacks: browse ───────────────────────────────────────────────────
for handler in browse_callback_handlers():
    app.add_handler(handler)

# ── Inline callbacks: visit (admin view) ──────────────────────────────────────
for handler in visit_callback_handlers():
    app.add_handler(handler)

# ── Inline callbacks: admin requests panel ────────────────────────────────────
app.add_handler(CallbackQueryHandler(cb_req_page,    pattern="^req_page_"))
app.add_handler(CallbackQueryHandler(cb_req_contact, pattern="^req_contact_"))
app.add_handler(CallbackQueryHandler(cb_req_delete,  pattern="^req_del_"))

# ── Channel import (must be before general message handler) ───────────────────
app.add_handler(channel_import_handler())

# ── Command + general message ─────────────────────────────────────────────────
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
