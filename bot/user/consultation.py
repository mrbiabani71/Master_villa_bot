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
from states import CONSULT_NAME, CONSULT_PHONE, CONSULT_REGION, CONSULT_BUDGET

try:
    from config import ADMIN_ID
except Exception:
    ADMIN_ID = None

REGIONS = ["🏖 ساحلی (محمودآباد، ایزدشهر، سرخرود)", "🌲 جنگلی (آمل، چمستان، نور)"]
REGION_KB = ReplyKeyboardMarkup([[r] for r in REGIONS], resize_keyboard=True)

BUDGETS = [
    "🟢 اقتصادی  (زیر ۷ میلیارد)",
    "🔵 متوسط  (۷ تا ۱۰ میلیارد)",
    "🟣 نیمه لوکس  (۱۰ تا ۱۵ میلیارد)",
    "🔴 لوکس  (بالای ۱۵ میلیارد)",
]
BUDGET_KB = ReplyKeyboardMarkup([[b] for b in BUDGETS], resize_keyboard=True)


async def start_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["consult"] = {}
    await update.message.reply_text(
        "📩 *درخواست مشاوره*\n\n"
        "برای ارتباط با مشاوران ما، لطفاً اطلاعات زیر را وارد کنید.\n\n"
        "👤 نام و نام خانوادگی خود را بنویسید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return CONSULT_NAME


async def handle_consult_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("لطفاً نام کامل خود را وارد کنید:")
        return CONSULT_NAME
    context.user_data["consult"]["name"] = name
    await update.message.reply_text(
        f"✅ ممنون {name} عزیز\n\n📞 شماره تماس خود را وارد کنید:"
    )
    return CONSULT_PHONE


async def handle_consult_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        await update.message.reply_text("لطفاً شماره تماس معتبر وارد کنید (مثال: ۰۹۱۲۳۴۵۶۷۸۹):")
        return CONSULT_PHONE
    context.user_data["consult"]["phone"] = phone
    await update.message.reply_text(
        "🗺 منطقه مورد نظر خود را انتخاب کنید:",
        reply_markup=REGION_KB,
    )
    return CONSULT_REGION


async def handle_consult_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in REGIONS:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:", reply_markup=REGION_KB
        )
        return CONSULT_REGION
    context.user_data["consult"]["region"] = text
    await update.message.reply_text(
        "💰 بودجه تقریبی شما چقدر است؟",
        reply_markup=BUDGET_KB,
    )
    return CONSULT_BUDGET


async def handle_consult_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in BUDGETS:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید:", reply_markup=BUDGET_KB
        )
        return CONSULT_BUDGET

    consult = context.user_data.get("consult", {})
    name   = consult.get("name", "—")
    phone  = consult.get("phone", "—")
    region = consult.get("region", "—")
    budget = text

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
        f"✅ *درخواست مشاوره شما ثبت شد!*\n\n"
        f"👤 نام: {name}\n"
        f"📞 تلفن: {phone}\n"
        f"📍 منطقه: {region}\n"
        f"💰 بودجه: {budget}\n\n"
        f"مشاوران ما در اسرع وقت با شما تماس خواهند گرفت. 🙏",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )

    if ADMIN_ID:
        try:
            await update.get_bot().send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"📩 *درخواست مشاوره جدید* (شماره {req_id})\n\n"
                    f"👤 نام: {name}\n"
                    f"📞 تلفن: {phone}\n"
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


async def cancel_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("consult", None)
    await update.message.reply_text(
        "درخواست مشاوره لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


def build_consultation_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📩 درخواست مشاوره$"), start_consultation),
        ],
        states={
            CONSULT_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_name)],
            CONSULT_PHONE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_phone)],
            CONSULT_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_region)],
            CONSULT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_consult_budget)],
        },
        fallbacks=[CommandHandler("cancel", cancel_consultation)],
    )
