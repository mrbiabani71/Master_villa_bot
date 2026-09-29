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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋 به ربات Master Villa خوش اومدی\nیکی از گزینه‌های زیر رو انتخاب کن:",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📄 دریافت کاتالوگ":
        await update.message.reply_text("کاتالوگ به زودی ارسال می‌شود 📄")

    elif text == "🎥 ویدیوها":
        await update.message.reply_text("ویدیوهای ویلاها به زودی اضافه می‌شود 🎥")

    elif text == "💰 قیمت روز":
        await update.message.reply_text("برای دریافت قیمت روز با مشاور تماس بگیر 📞")

    elif text == "📞 مشاوره رایگان":
        await update.message.reply_text(
            "برای مشاوره رایگان لطفاً نام و شماره تماس خود را ارسال کنید 📞"
        )

    elif text == "👑 پنل مدیریت":
        await handle_admin_panel(update, context)

    elif text in ADMIN_PANEL_BUTTONS:
        await handle_admin_buttons(update, context)

    else:
        await update.message.reply_text("لطفاً از منو استفاده کن 👇")


init_db()

app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# ── ConversationHandlers (order matters) ───────────────────────────────────────
app.add_handler(build_add_villa_conv())
app.add_handler(build_visit_conv())   # must precede browse callbacks (intercepts browse_visit_)
app.add_handler(build_browse_conv())

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

# ── Command + general message ─────────────────────────────────────────────────
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
