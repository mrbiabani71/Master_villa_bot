from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from keyboards import admin_panel_keyboard, settings_keyboard, get_main_keyboard

ADMIN_PANEL_BUTTONS = {"🏡 مدیریت ویلاها", "📋 درخواست‌ها", "📊 آمار", "⚙️ تنظیمات", "✏️ ویرایش ویلا", "⬅️ بازگشت"}
SETTINGS_BUTTONS = {"🏙 مدیریت شهرها", "📍 مدیریت مناطق", "⬅️ بازگشت"}


async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return
    context.user_data["admin_menu"] = "panel"
    await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel_keyboard)


async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return

    text = update.message.text
    current_menu = context.user_data.get("admin_menu", "panel")

    if text == "⬅️ بازگشت":
        if current_menu == "settings":
            context.user_data["admin_menu"] = "panel"
            await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel_keyboard)
        else:
            context.user_data.pop("admin_menu", None)
            await update.message.reply_text(
                "بازگشت به منوی اصلی.",
                reply_markup=get_main_keyboard(update.effective_user.id),
            )
        return

    if text == "📋 درخواست‌ها":
        from admin.requests import handle_requests_button
        await handle_requests_button(update, context)
        return

    if text == "⚙️ تنظیمات":
        context.user_data["admin_menu"] = "settings"
        await update.message.reply_text("⚙️ تنظیمات", reply_markup=settings_keyboard)
        return

    if text in SETTINGS_BUTTONS:
        await update.message.reply_text("این بخش در حال توسعه است.", reply_markup=settings_keyboard)
        return

    await update.message.reply_text("این بخش در حال توسعه است.", reply_markup=admin_panel_keyboard)
