from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
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

from config import ADMIN_ID
from database import get_villa_by_id, get_villa_by_code, insert_visit_request
from keyboards import get_main_keyboard
from states import VISIT_NAME, VISIT_PHONE
from utils import fmt_price

# ── Keyboard ───────────────────────────────────────────────────────────────────

PHONE_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("📱 اشتراک‌گذاری شماره تماس", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _admin_notification(
    villa: dict, name: str, phone: str, user_id: int
) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"🔔 *درخواست بازدید جدید*\n"
        f"\n"
        f"🏡 کد ویلا: `{villa['villa_code']}`\n"
        f"🏙 شهر: {villa.get('city', '—')}\n"
        f"💰 قیمت: {fmt_price(villa.get('price'))}\n"
        f"\n"
        f"👤 نام: {name}\n"
        f"📞 شماره: `{phone}`"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📞 تماس",          url=f"tel:{phone}"),
            InlineKeyboardButton("💬 پیام به کاربر", url=f"tg://user?id={user_id}"),
        ],
        [
            InlineKeyboardButton("🏡 مشاهده ویلا",  callback_data=f"admin_view_{villa['villa_code']}"),
        ],
    ])
    return text, kb


async def _finish_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    phone: str,
) -> int:
    user_id    = update.effective_user.id
    name       = context.user_data.get("visit_name", "—")
    villa      = context.user_data.get("visit_villa", {})
    villa_code = villa.get("villa_code", "—")

    insert_visit_request(
        villa_code=villa_code,
        user_id=user_id,
        name=name,
        phone=phone,
        area_type=villa.get("area_type", ""),
    )

    notif_text, notif_kb = _admin_notification(villa, name, phone, user_id)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=notif_text,
            parse_mode="Markdown",
            reply_markup=notif_kb,
        )
    except Exception:
        pass  # never let admin notification failure block the user confirmation

    context.user_data.pop("visit_villa", None)
    context.user_data.pop("visit_name",  None)

    await update.effective_message.reply_text(
        "✅ درخواست بازدید شما با موفقیت ثبت شد.\n"
        "کارشناسان ما به زودی با شما تماس می‌گیرند 🏡",
        reply_markup=get_main_keyboard(user_id),
    )
    return ConversationHandler.END

# ── Step handlers ──────────────────────────────────────────────────────────────

async def start_visit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # callback data: "browse_visit_{villa_id}"
    try:
        villa_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.message.reply_text("⚠️ خطا در پردازش درخواست. لطفاً دوباره امتحان کنید.")
        return ConversationHandler.END

    villa = get_villa_by_id(villa_id)
    if not villa or villa.get("status") != "active":
        await query.message.reply_text("⚠️ این ویلا در حال حاضر در دسترس نیست.")
        return ConversationHandler.END

    context.user_data["visit_villa"] = {
        "villa_code": villa["villa_code"],
        "city":       villa.get("city"),
        "price":      villa.get("price"),
        "area_type":  villa.get("area_type", ""),
    }

    await query.message.reply_text(
        f"☎️ *درخواست بازدید — ویلا {villa['villa_code']}*\n\n"
        f"لطفاً نام و نام خانوادگی خود را وارد کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return VISIT_NAME


async def handle_visit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("لطفاً نام کامل خود را وارد کنید:")
        return VISIT_NAME

    context.user_data["visit_name"] = name
    await update.message.reply_text(
        "📞 شماره تماس خود را وارد کنید یا از دکمه زیر استفاده کنید:",
        reply_markup=PHONE_KB,
    )
    return VISIT_PHONE


async def handle_visit_phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw    = update.message.text.strip()
    digits = raw.replace("+", "").replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) < 10:
        await update.message.reply_text(
            "⚠️ شماره تماس معتبر نیست. لطفاً دوباره وارد کنید:",
            reply_markup=PHONE_KB,
        )
        return VISIT_PHONE
    return await _finish_request(update, context, raw)


async def handle_visit_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.contact.phone_number
    return await _finish_request(update, context, phone)


async def cancel_visit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("visit_villa", None)
    context.user_data.pop("visit_name",  None)
    await update.message.reply_text(
        "درخواست بازدید لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END

# ── Admin callback: view villa details ────────────────────────────────────────

async def cb_admin_view_villa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("دسترسی مجاز نیست.", show_alert=True)
        return

    villa_code = query.data[len("admin_view_"):]
    villa      = get_villa_by_code(villa_code)

    if not villa:
        await query.message.reply_text("⚠️ ویلا یافت نشد.")
        return

    villa_type = "شهرکی" if villa.get("is_townhouse") else "مستقل"

    feature_parts = []
    if villa.get("has_pool"):        feature_parts.append("🏊 استخر")
    if villa.get("has_jacuzzi"):     feature_parts.append("🛁 جکوزی")
    if villa.get("has_roof_garden"): feature_parts.append("🌿 روف گاردن")
    if villa.get("has_parking"):     feature_parts.append("🚗 پارکینگ")
    if villa.get("has_storage"):     feature_parts.append("📦 انباری")
    features_str = "  |  ".join(feature_parts) if feature_parts else "—"

    text = (
        f"🏡 *ویلا {villa['villa_code']}*\n"
        f"\n"
        f"🏙 شهر: {villa.get('city', '—')}\n"
        f"🌊 منطقه: {villa.get('area_type', '—')}\n"
        f"🏡 نوع: {villa_type}\n"
        f"💰 قیمت: {fmt_price(villa.get('price'))}\n"
        f"📐 زمین: {villa.get('land_size', '—')} م²   🏗 بنا: {villa.get('building_size', '—')} م²\n"
        f"🛏 اتاق: {villa.get('bedrooms', '—')}\n"
        f"✨ امکانات: {features_str}\n"
        f"📄 سند: {villa.get('document_type', '—')}\n"
        f"🔖 وضعیت: {villa.get('status', '—')}\n"
        f"\n"
        f"📝 {villa.get('description') or '—'}"
    )

    await query.message.reply_text(text, parse_mode="Markdown")

# ── Factories ──────────────────────────────────────────────────────────────────

def build_visit_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_visit, pattern="^browse_visit_"),
        ],
        states={
            VISIT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_visit_name),
            ],
            VISIT_PHONE: [
                MessageHandler(filters.CONTACT, handle_visit_contact),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_visit_phone_text),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_visit),
        ],
        allow_reentry=True,   # user can press ☎️ on a different villa mid-flow
        per_message=False,    # track state per user+chat (not per message)
    )


def visit_callback_handlers() -> list:
    return [
        CallbackQueryHandler(cb_admin_view_villa, pattern="^admin_view_"),
    ]
