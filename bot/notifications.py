"""
Notification dispatcher — called after a new villa is confirmed created.

Usage (fire-and-forget):
    asyncio.create_task(dispatch_new_villa_notification(bot, villa_id))

Does NOT import anything from channel_importer or admin flows.
"""
from __future__ import annotations

import logging

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_all_active_prefs
from pg_villas import get_villa_by_id
from utils import fmt_price, price_category

logger = logging.getLogger(__name__)


# ── Matching ───────────────────────────────────────────────────────────────────

def _matches(villa: dict, prefs: dict) -> bool:
    area = prefs.get("area_type")
    if area:
        if villa.get("area_type") != area:
            return False

    min_p = prefs.get("min_price")
    max_p = prefs.get("max_price")
    price = villa.get("price") or 0
    if min_p is not None and price < min_p:
        return False
    if max_p is not None and price > max_p:
        return False

    vtype = prefs.get("villa_type")
    if vtype:
        expected = 1 if vtype == "شهرکی" else 0
        if villa.get("is_townhouse", 0) != expected:
            return False

    return True


# ── Message builder ────────────────────────────────────────────────────────────

def _notification_text(villa: dict) -> str:
    features = []
    if villa.get("has_pool"):        features.append("🏊 استخر")
    if villa.get("has_jacuzzi"):     features.append("🛁 جکوزی")
    if villa.get("has_roof_garden"): features.append("🌿 روف‌گاردن")
    if villa.get("has_parking"):     features.append("🚗 پارکینگ")
    if villa.get("has_storage"):     features.append("📦 انباری")
    features_line = "   |   ".join(features) if features else "—"

    villa_type = "شهرکی" if villa.get("is_townhouse") else "مستقل"
    price = fmt_price(villa.get("price"))
    cat   = price_category(villa.get("price"))

    return (
        f"🔔 *ویلای جدید متناسب با ترجیحات شما*\n\n"
        f"🏡 *ویلا {villa['villa_code']}*\n"
        f"📍 {villa.get('city', '—')}  ·  {villa.get('area_type', '—')}  ·  {villa_type}\n"
        f"💰 {price}  {cat}\n"
        f"📐 زمین: {villa.get('land_size', '—')} م²   "
        f"بنا: {villa.get('building_size', '—')} م²   "
        f"🛏 {villa.get('bedrooms', '—')} اتاق\n"
        f"✨ {features_line}"
    )


def _notification_kb(villa_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁 مشاهده ویلا", callback_data=f"browse_detail_{villa_id}")],
        [InlineKeyboardButton("🔕 لغو اعلان‌ها", callback_data="notif_disable")],
    ])


# ── Dispatcher ─────────────────────────────────────────────────────────────────

async def dispatch_new_villa_notification(bot: Bot, villa_id: int) -> None:
    """
    Fire-and-forget: fetch the new villa, find matching subscribers, notify each.
    Any exception is caught and logged — never propagates to the caller.
    """
    try:
        villa = get_villa_by_id(villa_id)
        if not villa:
            logger.warning("NOTIFY | villa_id=%s not found — skipping", villa_id)
            return

        prefs_list = get_all_active_prefs()
        if not prefs_list:
            return

        text   = _notification_text(villa)
        kb     = _notification_kb(villa_id)
        photos = [p for p in (villa.get("photos") or "").split(",") if p]
        sent   = 0

        for prefs in prefs_list:
            if not _matches(villa, prefs):
                continue
            uid = prefs["user_id"]
            try:
                if photos:
                    await bot.send_photo(
                        chat_id=uid,
                        photo=photos[0],
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=kb,
                    )
                else:
                    await bot.send_message(
                        chat_id=uid,
                        text=text,
                        parse_mode="Markdown",
                        reply_markup=kb,
                    )
                sent += 1
            except Exception as exc:
                logger.warning("NOTIFY | failed to reach user_id=%s: %s", uid, exc)

        logger.info(
            "NOTIFY | villa=%s — %d / %d subscribers notified",
            villa["villa_code"], sent, len(prefs_list),
        )
    except Exception:
        logger.exception("NOTIFY | unhandled error for villa_id=%s", villa_id)
