from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from database import get_user_compare, clear_compare
from pg_villas import get_villa_by_id
from utils import fmt_price


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _yn(val) -> str:
    return "✅" if val else "❌"


def _amenities(villa: dict) -> str:
    parts = []
    if villa.get("has_pool"):        parts.append("استخر")
    if villa.get("has_jacuzzi"):     parts.append("جکوزی")
    if villa.get("has_roof_garden"): parts.append("روف‌گاردن")
    if villa.get("has_parking"):     parts.append("پارکینگ")
    if villa.get("has_storage"):     parts.append("انباری")
    return "  ،  ".join(parts) if parts else "—"


def _row(label: str, values: list[str]) -> str:
    return f"{label}\n   " + "   |   ".join(values)


def _build_compare_text(villas: list[dict]) -> str:
    n     = len(villas)
    codes = "   |   ".join(f"*{v['villa_code']}*" for v in villas)

    sections: list[str] = [
        f"⚖️ *مقایسه {n} ویلا*",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"🏷  {codes}",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]

    def vals(key: str, suffix: str = "") -> list[str]:
        return [str(v.get(key) or "—") + suffix for v in villas]

    # Location
    sections.append(_row("🌊 *منطقه:*",  vals("area_type")))
    sections.append(_row("📍 *شهر:*",    vals("city")))

    sections.append("─" * 26)

    # Dimensions
    sections.append(_row("📐 *زمین:*",  [str(v.get("land_size") or "—") + " م²"     for v in villas]))
    sections.append(_row("🏗 *بنا:*",   [str(v.get("building_size") or "—") + " م²" for v in villas]))
    sections.append(_row("🛏 *اتاق:*",  vals("bedrooms")))

    sections.append("─" * 26)

    # Legal / community
    sections.append(_row("📄 *سند:*",    vals("document_type")))
    sections.append(_row(
        "🏘 *شهرک:*",
        [v.get("community_status") or ("داخل شهرک" if v.get("is_townhouse") else "مستقل") for v in villas],
    ))

    sections.append("─" * 26)

    # Appearance & services
    sections.append(_row("🪟 *نما:*",       vals("facade")))
    sections.append(_row("🔌 *اشتراکات:*",  vals("utilities")))
    sections.append(_row("✨ *امکانات:*",   [_amenities(v) for v in villas]))

    sections.append("━━━━━━━━━━━━━━━━━━━━━━")

    # Price — on its own line, prominent
    sections.append(_row("💰 *قیمت:*",  [fmt_price(v.get("price")) for v in villas]))

    sections.append("━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(sections)


def _compare_kb(villas: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard: one 👁 button per villa, then 🗑 clear."""
    view_row = [
        InlineKeyboardButton(
            f"👁 {v['villa_code']}",
            callback_data=f"browse_detail_{v['id']}",
        )
        for v in villas
    ]
    return InlineKeyboardMarkup([
        view_row,
        [InlineKeyboardButton("🗑 پاک کردن لیست مقایسه", callback_data="cmp_clear")],
    ])


# ── Shared rendering ───────────────────────────────────────────────────────────

async def _render_comparison(chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """
    Fetch compare list, build text + keyboard, send one message.
    Returns True on success, False if not enough villas.
    Callers must handle the 0/1 villa edge-cases before calling this.
    """
    villa_ids = get_user_compare(user_id)
    villas    = [v for vid in villa_ids if (v := get_villa_by_id(vid))]

    if len(villas) < 2:
        return False

    text = _build_compare_text(villas)
    kb   = _compare_kb(villas)

    await context.bot.send_message(
        chat_id    = chat_id,
        text       = text,
        parse_mode = "Markdown",
        reply_markup = kb,
    )
    return True


# ── Public handlers ────────────────────────────────────────────────────────────

async def show_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point from the ⚖️ مقایسه ویلاها menu button."""
    user_id   = update.effective_user.id
    chat_id   = update.effective_chat.id
    villa_ids = get_user_compare(user_id)
    n         = len(villa_ids)

    if n == 0:
        await update.message.reply_text(
            "⚖️ *مقایسه ویلاها*\n\n"
            "هیچ ویلایی برای مقایسه انتخاب نشده است.\n"
            "هنگام مشاهده ویلا روی *⚖️ افزودن برای مقایسه* بزنید.\n\n"
            "_حداکثر ۳ ویلا را می‌توانید با هم مقایسه کنید._",
            parse_mode="Markdown",
        )
        return

    if n == 1:
        vid   = villa_ids[0]
        villa = get_villa_by_id(vid)
        name  = villa["villa_code"] if villa else f"#{vid}"
        await update.message.reply_text(
            f"⚖️ *مقایسه ویلاها*\n\n"
            f"فقط ویلای *{name}* انتخاب شده است.\n"
            f"برای مقایسه حداقل ۲ ویلا لازم است.\n\n"
            f"_روی کارت ویلاها گزینه ⚖️ را بزنید تا اضافه شوند._",
            parse_mode="Markdown",
        )
        return

    await _render_comparison(chat_id, context, user_id)


async def cb_show_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for the 📊 نمایش مقایسه inline button on villa cards."""
    query   = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    ok = await _render_comparison(chat_id, context, user_id)
    if ok:
        await query.answer()
    else:
        await query.answer(
            "برای مقایسه حداقل ۲ ویلا لازم است.",
            show_alert=True,
        )


async def cb_clear_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for the 🗑 clear button inside the comparison message."""
    query   = update.callback_query
    user_id = query.from_user.id
    clear_compare(user_id)
    await query.answer("🗑 لیست مقایسه پاک شد")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
