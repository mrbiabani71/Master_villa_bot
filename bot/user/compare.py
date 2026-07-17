from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from database import get_user_compare, clear_compare
from pg_villas import get_villa_by_id
from utils import fmt_price, price_category


# ── Helpers ────────────────────────────────────────────────────────────────────

def _yn(val) -> str:
    return "✅" if val else "❌"


def _feature_row(label: str, villas: list[dict], key: str) -> str:
    vals = "   |   ".join(_yn(v.get(key)) for v in villas)
    return f"  {label:<14} {vals}"


def _text_row(label: str, villas: list[dict], key: str, suffix: str = "") -> str:
    vals = "   |   ".join(str(v.get(key) or "—") + suffix for v in villas)
    return f"  {label:<14} {vals}"


def _build_compare_text(villas: list[dict]) -> str:
    n = len(villas)
    codes = "   |   ".join(f"*{v['villa_code']}*" for v in villas)

    lines = [
        f"⚖️ *مقایسه {n} ویلا*\n",
        f"  {'':14} {codes}",
        "  " + "─" * 44,
    ]

    # Price
    prices = "   |   ".join(fmt_price(v.get("price")) for v in villas)
    lines.append(f"  {'💰 قیمت':<14} {prices}")

    # Location
    cities  = "   |   ".join(str(v.get("city") or "—")      for v in villas)
    areas   = "   |   ".join(str(v.get("area_type") or "—") for v in villas)
    lines.append(f"  {'📍 شهر':<14} {cities}")
    lines.append(f"  {'🌊 منطقه':<14} {areas}")

    lines.append("  " + "─" * 44)

    # Sizes
    lands  = "   |   ".join(str(v.get("land_size") or "—") + " م²"     for v in villas)
    builds = "   |   ".join(str(v.get("building_size") or "—") + " م²" for v in villas)
    rooms  = "   |   ".join(str(v.get("bedrooms") or "—") + " اتاق"    for v in villas)
    lines.append(f"  {'📐 زمین':<14} {lands}")
    lines.append(f"  {'🏗 بنا':<14} {builds}")
    lines.append(f"  {'🛏 اتاق':<14} {rooms}")

    lines.append("  " + "─" * 44)

    # Features
    lines.append(_feature_row("🏊 استخر",      villas, "has_pool"))
    lines.append(_feature_row("🛁 جکوزی",     villas, "has_jacuzzi"))
    lines.append(_feature_row("🌿 روف گاردن", villas, "has_roof_garden"))
    lines.append(_feature_row("🚗 پارکینگ",   villas, "has_parking"))
    lines.append(_feature_row("📦 انباری",    villas, "has_storage"))

    lines.append("  " + "─" * 44)

    # Document & type
    docs  = "   |   ".join(str(v.get("document_type") or "—") for v in villas)
    types = "   |   ".join("شهرکی" if v.get("is_townhouse") else "مستقل" for v in villas)
    lines.append(f"  {'📄 سند':<14} {docs}")
    lines.append(f"  {'🏡 نوع':<14} {types}")

    lines.append("")
    lines.append("_برای حذف لیست مقایسه دکمه زیر را بزنید:_")

    return "\n".join(lines)


def _clear_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 پاک کردن لیست مقایسه", callback_data="cmp_clear")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def show_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id   = update.effective_user.id
    villa_ids = get_user_compare(user_id)

    if not villa_ids:
        await update.message.reply_text(
            "⚖️ *مقایسه ویلاها*\n\n"
            "هیچ ویلایی برای مقایسه انتخاب نشده است.\n"
            "هنگام مشاهده ویلا روی *⚖️ افزودن برای مقایسه* بزنید.\n\n"
            "_می‌توانید حداکثر ۳ ویلا را با هم مقایسه کنید._",
            parse_mode="Markdown",
        )
        return

    if len(villa_ids) == 1:
        villa = get_villa_by_id(villa_ids[0])
        name  = villa["villa_code"] if villa else f"#{villa_ids[0]}"
        await update.message.reply_text(
            f"⚖️ *مقایسه ویلاها*\n\n"
            f"فقط ویلای *{name}* انتخاب شده است.\n"
            f"حداقل ۲ ویلا برای مقایسه لازم است.\n\n"
            f"_می‌توانید حداکثر ۳ ویلا اضافه کنید._",
            parse_mode="Markdown",
            reply_markup=_clear_kb(),
        )
        return

    villas = []
    for vid in villa_ids:
        v = get_villa_by_id(vid)
        if v:
            villas.append(v)

    if len(villas) < 2:
        await update.message.reply_text(
            "⚠️ اطلاعات ویلاهای انتخاب‌شده در دسترس نیست.",
            reply_markup=_clear_kb(),
        )
        return

    text = _build_compare_text(villas)
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=_clear_kb(),
    )


async def cb_clear_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    user_id = query.from_user.id
    clear_compare(user_id)
    await query.answer("🗑 لیست مقایسه پاک شد")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
