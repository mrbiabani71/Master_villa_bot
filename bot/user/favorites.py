from telegram import Update
from telegram.ext import ContextTypes

from database import get_user_favorites
from pg_villas import get_villa_by_id
from user.browse import _send_villa_card


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id  = update.effective_user.id
    villa_ids = get_user_favorites(user_id)

    if not villa_ids:
        await update.message.reply_text(
            "❤️ *علاقه‌مندی‌های شما*\n\n"
            "هنوز هیچ ویلایی ذخیره نکرده‌اید.\n"
            "هنگام مشاهده ویلا روی *❤️ افزودن به علاقه‌مندی‌ها* بزنید.",
            parse_mode="Markdown",
        )
        return

    # Fetch villa details from PostgreSQL via the API
    villas = []
    for vid in villa_ids:
        v = get_villa_by_id(vid)
        if v:
            villas.append(v)

    if not villas:
        await update.message.reply_text(
            "❤️ *علاقه‌مندی‌های شما*\n\n"
            "ویلاهای ذخیره‌شده دیگر در دسترس نیستند.",
            parse_mode="Markdown",
        )
        return

    # Reuse the standard browse pagination — populate browse_results so that
    # the existing browse_next / browse_detail callbacks work automatically.
    context.user_data["browse_results"] = villas
    context.user_data["browse_idx"]     = 0

    await update.message.reply_text(
        f"❤️ *علاقه‌مندی‌های شما* — {len(villas)} ویلا",
        parse_mode="Markdown",
    )
    await _send_villa_card(
        update.effective_chat.id, context, villas[0], 0, len(villas), user_id
    )
