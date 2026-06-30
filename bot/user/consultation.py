from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from database import insert_visit_request
from keyboards import get_main_keyboard
from states import CONSULT_NAME, CONSULT_PHONE, CONSULT_REGION, CONSULT_BUDGET, CONSULT_CONFIRM

try:
    from config import ADMIN_ID
except Exception:
    ADMIN_ID = None

BACK = "🔙 بازگشت"

REGIONS = [
    "🏖 ساحلی  (محمودآباد، ایزدشهر، سرخرود)",
    "🌲 جنگلی  (نور، آمل، چمستان)",
]
REGION_KB = ReplyKeyboardMarkup(
    [[r] for r in REGIONS] + [[BACK]],
    resize_keyboard=True,
)

BUDGETS = [
    "🟢 اقتصادی    (زیر ۷ میلیارد)",
    "🔵 متوسط      (۷ تا ۱۰ میلیارد)",
    "🟣 نیمه لوکس  (۱۰ تا ۱۵ میلیارد)",
    "🔴 لوکس       (بالای ۱۵ میلیارد)",
]
BUDGET_KB = ReplyKeyboardMarkup(
    [[b] for b in BUDGETS] + [[BACK]],
    resize_keyboard=True,
)

CONFIRM_KB = ReplyKeyboardMarkup(
    [["✅ تایید و ارسال"], [BACK]],
    resize_keyboard=True,
)

# ── Entry ──────────────────────────────────────────────────────────────────────

async def start_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["consult"] = {}
    await update.message.reply_text(
        "📩 *درخواست مشاوره رایگان*\n\n"
        "مشاوران ما در اسرع وقت با شما تماس خواهند گرفت.\n\n"
        "👤 نام و نام خانوادگی خود را بنویسید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[BACK]], resize_keyboard=True),
    )
    return CONSULT_NAME

# ── Step 1: name ───────────────────────────────────────────────────────────────

async def handle_consult_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        context.user_data.pop("consult", None)
        await update.message.reply_text(
            "به منوی اصلی بازگشتید.",
            reply_markup=get_main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END

    if len(text) < 2:
        await update.message.reply_text(
            "لطفاً نام کامل خود را وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([[BACK]], resize_keyboard=True),
        )
        return CONSULT_NAME

    context.user_data["consult"]["name"] = text
    await update.message.reply_text(
        f"✅ ممنون *{text}* عزیز\n\n"
        f"📞 شماره تماس خود را وارد کنید:\n"
        f"_(مثال: ۰۹۱۲۳۴۵۶۷۸۹)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[BACK]], resize_keyboard=True),
    )
    return CONSULT_PHONE

# ── Step 2: phone ──────────────────────────────────────────────────────────────

async def handle_consult_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        name = context.user_data.get("consult", {}).get("name", "")
        await update.message.reply_text(
            "👤 نام و نام خانوادگی خود را بنویسید:",
            reply_markup=ReplyKeyboardMarkup([[BACK]], resize_keyboard=True),
        )
        return CONSULT_NAME

    digits = "".join(c for c in text if c.isdigit())
    if len(digits) < 10:
        await update.message.reply_text(
            "⚠️ شماره تماس معتبر نیست.\n"
            "لطفاً دوباره وارد کنید (مثال: ۰۹۱۲۳۴۵۶۷۸۹):",
            reply_markup=ReplyKeyboardMarkup([[BACK]], resize_keyboard=True),
        )
        return CONSULT_PHONE

    context.user_data["consult"]["phone"] = text
    await update.message.reply_text(
        "🗺 منطقه مورد نظر خود را انتخاب کنید:",
        reply_markup=REGION_KB,
    )
    return CONSULT_REGION

# ── Step 3: region ─────────────────────────────────────────────────────────────

async def handle_consult_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        await update.message.reply_text(
            "📞 شماره تماس خود را وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([[BACK]], resize_keyboard=True),
        )
        return CONSULT_PHONE

    if text not in REGIONS:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=REGION_KB,
        )
        return CONSULT_REGION

    context.user_data["consult"]["region"] = text
    await update.message.reply_text(
        "💰 بودجه تقریبی خود را انتخاب کنید:",
        reply_markup=BUDGET_KB,
    )
    return CONSULT_BUDGET

# ── Step 4: budget → confirmation ─────────────────────────────────────────────

async def handle_consult_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        await update.message.reply_text(
            "🗺 منطقه مورد نظر خود را انتخاب کنید:",
            reply_markup=REGION_KB,
        )
        return CONSULT_REGION

    if text not in BUDGETS:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:",
            reply_markup=BUDGET_KB,
        )
        return CONSULT_BUDGET

    context.user_data["consult"]["budget"] = text
    c = context.user_data["consult"]

    await update.message.reply_text(
        "📋 *خلاصه درخواست مشاوره شما:*\n\n"
        f"👤 نام: {c['name']}\n"
        f"📞 تلفن: {c['phone']}\n"
        f"📍 منطقه: {c['region']}\n"
        f"💰 بودجه: {c['budget']}\n\n"
        "آیا اطلاعات صحیح است؟",
        parse_mode="Markdown",
        reply_markup=CONFIRM_KB,
    )
    return CONSULT_CONFIRM

# ── Step 5: confirm & submit ───────────────────────────────────────────────────

async def handle_consult_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == BACK:
        await update.message.reply_text(
            "💰 بودجه تقریبی خود را انتخاب کنید:",
            reply_markup=BUDGET_KB,
        )
        return CONSULT_BUDGET

    if text != "✅ تایید و ارسال":
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=CONFIRM_KB,
        )
        return CONSULT_CONFIRM

    c = context.user_data.get("consult", {})
    name   = c.get("name",   "—")
    phone  = c.get("phone",  "—")
    region = c.get("region", "—")
    budget = c.get("budget", "—")

    region_short = "ساحلی" if "ساحلی" in region else "جنگلی"

    req_id = insert_visit_request(
        villa_code="مشاوره",
        user_id=update.effective_user.id,
        name=name,
        phone=phone,
        area_type=region_short,
        request_type="consultation",
    )

    await update.message.reply_text(
        "✅ *درخواست مشاوره شما ثبت شد!*\n\n"
        f"👤 نام: {name}\n"
        f"📞 تلفن: {phone}\n"
        f"📍 منطقه: {region}\n"
        f"💰 بودجه: {budget}\n\n"
        "🏡 مشاوران ما به زودی با شما تماس می‌گیرند.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )

    if ADMIN_ID:
        try:
            await update.get_bot().send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"📩 *درخواست مشاوره جدید* — شماره {req_id}\n\n"
                    f"👤 نام: {name}\n"
                    f"📞 تلفن: `{phone}`\n"
                    f"📍 منطقه: {region}\n"
                    f"💰 بودجه: {budget}\n"
                    f"🆔 کاربر: {update.effective_user.id}"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

    context.user_data.pop("consult", None)
    return ConversationHandler.END

# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("consult", None)
    await update.message.reply_text(
        "درخواست مشاوره لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END

# ── Factory ───────────────────────────────────────────────────────────────────

def build_consultation_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📩 درخواست مشاوره$"), start_consultation),
        ],
        states={
            CONSULT_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_name)],
            CONSULT_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_phone)],
            CONSULT_REGION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_region)],
            CONSULT_BUDGET:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_budget)],
            CONSULT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_confirm)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_consultation),
            CommandHandler("start",  cancel_consultation),
        ],
    )
