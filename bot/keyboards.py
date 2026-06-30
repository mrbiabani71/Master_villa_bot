from telegram import ReplyKeyboardMarkup

from config import ADMIN_ID

_user_menu = [
    ["🔍 جستجو ویلا"],
    ["📩 درخواست مشاوره"],
    ["❓ سوالات پرتکرار", "ℹ️ درباره ما"],
]

_admin_menu = _user_menu + [["👑 پنل مدیریت"]]

main_keyboard = ReplyKeyboardMarkup(_user_menu, resize_keyboard=True)
admin_main_keyboard = ReplyKeyboardMarkup(_admin_menu, resize_keyboard=True)

admin_panel_keyboard = ReplyKeyboardMarkup(
    [
        ["➕ ثبت ویلا", "📋 درخواست‌ها"],
        ["📊 آمار", "⚙️ تنظیمات"],
    ],
    resize_keyboard=True,
)


def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    if user_id == ADMIN_ID:
        return admin_main_keyboard
    return main_keyboard
