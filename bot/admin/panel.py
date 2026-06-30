from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from keyboards import admin_panel_keyboard, get_main_keyboard

ADMIN_PANEL_BUTTONS = {"📋 درخواست‌ها", "📊 آمار", "⚙️ تنظیمات"}


async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return
    await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel_keyboard)


async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return

    text = update.message.text

    if text == "📋 درخواست‌ها":
        from admin.requests import handle_requests_button
        await handle_requests_button(update, context)

    else:
        await update.message.reply_text("این بخش در حال توسعه است.")
