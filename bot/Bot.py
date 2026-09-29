import os
import warnings
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=Warning)

import logging
import datetime

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
    ContextTypes,
    MessageReactionHandler,   # 🔥 NEW
)

_debug_logger = logging.getLogger("bot.update_debug")

from config import TELEGRAM_BOT_TOKEN
from keyboards import get_main_keyboard
from database_main import (
    init_db,
    register_user,
    log_activity,
    get_connection
)

# 🔥 NEW — هندلر ری‌اکشن‌ها
from user.reaction_handler import handle_reaction

from admin.panel import ADMIN_PANEL_BUTTONS, SETTINGS_BUTTONS, handle_admin_panel, handle_admin_buttons
from admin.channel_import_panel import cb_import_confirm, cb_import_cancel
from admin.smart_import_flow import build_smart_import_conv
from admin.edit_villa_flow import build_edit_villa_conv
from admin.manage_villas import build_manage_villas_conv
from admin.requests import cb_req_page, cb_req_contact, cb_req_delete
from user.browse import build_browse_conv, browse_callback_handlers
from user.advanced_search import build_advanced_search_conv
from user.visit import build_visit_conv, visit_callback_handlers
from user.consultation import build_consultation_conv
from user.faq import show_faq_menu, faq_callback_handlers
from user.favorites import show_favorites
from user.compare import show_compare, cb_show_compare, cb_clear_compare
from user.notify_prefs import build_notify_prefs_conv, cb_notif_disable
from channel_importer import channel_import_handler

FAQ_TEXT = (
    "❓ *سوالات پرتکرار*\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "📄 *سند ملک چه نوعی است؟*\n"
    "اکثر ویلاهای ما دارای سند تک‌برگ یا سند منگوله‌دار هستند.\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "🏡 *آیا بازدید حضوری امکان‌پذیر است؟*\n"
    "بله، پس از ثبت درخواست بازدید هماهنگ می‌شود.\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "💳 *روش پرداخت؟*\n"
    "معاملات با حضور کارشناس حقوقی انجام می‌شود.\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "📍 *مناطق فعالیت؟*\n"
    "ساحلی و جنگلی در مازندران.\n\n"
)

ABOUT_TEXT = (
    "ℹ️ *درباره مستر ویلا*\n\n"
    "مجموعه تخصصی خرید و فروش ویلاهای شمال ایران.\n\n"
)

# ───────────────────────────────────────────────
# ثبت کاربر + ثبت فعالیت
# ───────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    log_activity("start")
    await update.message.reply_text(
        "سلام 👋 به ربات *Master Villa* خوش اومدی\n"
        "برای جستجوی ویلا یا درخواست مشاوره از منو استفاده کن:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    text = update.message.text

    if text == "❤️ علاقه‌مندی‌ها":
        log_activity("favorites")
        await show_favorites(update, context)

    elif text == "⚖️ مقایسه ویلاها":
        log_activity("compare")
        await show_compare(update, context)

    elif text == "❓ سوالات پرتکرار":
        log_activity("faq")
        await show_faq_menu(update, context)

    elif text == "ℹ️ درباره ما":
        log_activity("about")
        await update.message.reply_text(ABOUT_TEXT, parse_mode="Markdown")

    elif text == "👑 پنل مدیریت":
        log_activity("admin_panel")
        await handle_admin_panel(update, context)

    elif text in ADMIN_PANEL_BUTTONS or text in SETTINGS_BUTTONS:
        log_activity("admin_button")
        await handle_admin_buttons(update, context)

    else:
        log_activity("unknown_message")
        await update.message.reply_text(
            "لطفاً از منو استفاده کن 👇",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )


init_db()

# ───────────────────────────────────────────────
# گزارش روزانه
# ───────────────────────────────────────────────

def generate_daily_report() -> str:
    with get_connection() as conn:
        views = conn.execute("SELECT COUNT(*) FROM activity_log WHERE type='view_villa'").fetchone()[0]
        favorites = conn.execute("SELECT COUNT(*) FROM activity_log WHERE type='favorites'").fetchone()[0]
        compares = conn.execute("SELECT COUNT(*) FROM activity_log WHERE type='compare'").fetchone()[0]
        searches = conn.execute("SELECT COUNT(*) FROM activity_log WHERE type='search'").fetchone()[0]
        visits = conn.execute("SELECT COUNT(*) FROM activity_log WHERE type='visit_request'").fetchone()[0]
        active_users = conn.execute("SELECT COUNT(*) FROM users WHERE last_active >= datetime('now','-1 day')").fetchone()[0]

    return (
        "📊 *گزارش روزانه ربات*\n\n"
        f"👁 بازدید ویلاها: {views}\n"
        f"❤️ علاقه‌مندی‌ها: {favorites}\n"
        f"⚖️ مقایسه‌ها: {compares}\n"
        f"🔍 جستجوها: {searches}\n"
        f"📅 درخواست‌های بازدید: {visits}\n"
        f"👤 کاربران فعال ۲۴ ساعت اخیر: {active_users}\n"
    )


async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    report = generate_daily_report()
    admin_id = 000000000
    await context.bot.send_message(chat_id=admin_id, text=report, parse_mode="Markdown")


# ───────────────────────────────────────────────
# DEBUG
# ───────────────────────────────────────────────

async def _log_startup_identity(application: Application) -> None:
    me = await application.bot.get_me()
    _debug_logger.warning(
        "DEBUG_STARTUP | running as @%s (id=%s, name=%s)",
        me.username, me.id, me.first_name,
    )


async def _log_every_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    update_type = next(
        (
            name
            for name, val in [
                ("message", update.message),
                ("edited_message", update.edited_message),
                ("channel_post", update.channel_post),
                ("edited_channel_post", update.edited_channel_post),
                ("callback_query", update.callback_query),
                ("my_chat_member", update.my_chat_member),
                ("chat_member", update.chat_member),
            ]
            if val is not None
        ),
        "other",
    )
    chat_id = update.effective_chat.id if update.effective_chat else None
    _debug_logger.warning(
        "DEBUG_UPDATE | type=%s update_id=%s chat_id=%s",
        update_type, update.update_id, chat_id,
    )


# ───────────────────────────────────────────────
# APP
# ───────────────────────────────────────────────

app = (
    ApplicationBuilder()
    .token(TELEGRAM_BOT_TOKEN)
    .post_init(_log_startup_identity)
    .build()
)

# زمان‌بندی گزارش روزانه ساعت ۲۲
app.job_queue.run_daily(
    send_daily_report,
    time=datetime.time(hour=22, minute=0)
)

# DEBUG
app.add_handler(TypeHandler(Update, _log_every_update), group=-1)

# 🔥 NEW — هندلر ری‌اکشن‌ها
app.add_handler(MessageReactionHandler(handle_reaction))

# ConversationHandlers
app.add_handler(build_smart_import_conv())
app.add_handler(build_edit_villa_conv())
app.add_handler(build_manage_villas_conv())
app.add_handler(build_consultation_conv())
app.add_handler(build_visit_conv())
app.add_handler(build_advanced_search_conv())
app.add_handler(build_browse_conv())
app.add_handler(build_notify_prefs_conv())

# FAQ callbacks
for handler in faq_callback_handlers():
    app.add_handler(handler)

# Browse callbacks
for handler in browse_callback_handlers():
    app.add_handler(handler)

# Visit callbacks
for handler in visit_callback_handlers():
    app.add_handler(handler)

# Admin request callbacks
app.add_handler(CallbackQueryHandler(cb_req_page,    pattern="^req_page_"))
app.add_handler(CallbackQueryHandler(cb_req_contact, pattern="^req_contact_"))
app.add_handler(CallbackQueryHandler(cb_req_delete,  pattern="^req_del_"))

# Channel import callbacks
app.add_handler(CallbackQueryHandler(cb_import_confirm,  pattern="^ch_import_confirm$"))
app.add_handler(CallbackQueryHandler(cb_import_cancel,   pattern="^ch_import_cancel$"))
app.add_handler(CallbackQueryHandler(cb_show_compare,    pattern="^cmp_view$"))
app.add_handler(CallbackQueryHandler(cb_clear_compare,   pattern="^cmp_clear$"))
app.add_handler(CallbackQueryHandler(cb_notif_disable,   pattern="^notif_disable$"))

# Channel import handler
app.add_handler(channel_import_handler())

# Commands + general messages
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()