"""
Channel importer — watches the configured Telegram channel for new villa posts,
parses the fixed emoji-prefixed template, and saves villas + photos to the DB.

Template format (send as caption on first photo of a media group, or as plain text):

🏡 MV-1001          ← villa code (or AUTO to let the bot generate one)
📍 محمودآباد         ← city
💰 ۲.۵ میلیارد      ← price  (Persian/Western digits + میلیارد/میلیون accepted)
📐 ۳۰۰              ← land size in m²
🏠 ۱۵۰              ← building size in m²
🛏 ۳                ← number of bedrooms
📄 تک‌برگ            ← document type
✨ استخر، جکوزی، پارکینگ   ← optional features
📝 توضیحات ویلا…    ← optional description

Bot must be admin of the channel to receive posts.
"""

import asyncio
import logging
import re
from telegram import Update, Bot
from telegram.ext import ContextTypes, MessageHandler, filters

from config import ADMIN_ID, CHANNEL_ID
from database import insert_villa, get_villa_by_code, get_next_villa_code

logger = logging.getLogger(__name__)

# ── Mapping tables ─────────────────────────────────────────────────────────────

CITY_AREA_MAP: dict[str, str] = {
    "محمودآباد": "ساحلی",
    "سرخرود":    "ساحلی",
    "ایزدشهر":   "ساحلی",
    "نور":       "جنگلی",
    "آمل":       "جنگلی",
    "چمستان":    "جنگلی",
}

FEATURE_MAP: dict[str, str] = {
    "استخر":     "has_pool",
    "جکوزی":    "has_jacuzzi",
    "روف گاردن": "has_roof_garden",
    "روف‌گاردن": "has_roof_garden",
    "پارکینگ":  "has_parking",
    "انباری":   "has_storage",
}

FIELD_PREFIXES = [
    ("🏡", "code"),
    ("📍", "city"),
    ("💰", "price"),
    ("📐", "land"),
    ("🏠", "building"),
    ("🛏", "bedrooms"),
    ("📄", "document"),
    ("✨", "features"),
    ("📝", "description"),
]

# ── Number parsing ─────────────────────────────────────────────────────────────

_PERSIAN_ARABIC = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _to_latin(text: str) -> str:
    return text.translate(_PERSIAN_ARABIC)


def _parse_price(text: str) -> float | None:
    """Parse prices like '۲.۵ میلیارد', '800 میلیون', '1500000000'."""
    text = _to_latin(text).strip()
    multiplier = 1
    if "میلیارد" in text:
        multiplier = 1_000_000_000
        text = text.replace("میلیارد", "").strip()
    elif "میلیون" in text:
        multiplier = 1_000_000
        text = text.replace("میلیون", "").strip()
    m = re.search(r"[\d.]+", text)
    if not m:
        return None
    try:
        return float(m.group()) * multiplier
    except ValueError:
        return None


def _parse_float(text: str) -> float | None:
    m = re.search(r"[\d.]+", _to_latin(text))
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _parse_int(text: str) -> int | None:
    m = re.search(r"\d+", _to_latin(text))
    return int(m.group()) if m else None


# ── Template parser ────────────────────────────────────────────────────────────

def parse_villa_post(text: str) -> dict | None:
    """
    Parse a channel post into a villa data dict.
    Returns None if required fields (city, price) are missing.
    """
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    logger.debug(
        "CHANNEL_IMPORT | raw post (%d chars, %d lines):\n%s",
        len(text), len(lines), text,
    )

    raw: dict[str, str] = {}
    for line in lines:
        for emoji, key in FIELD_PREFIXES:
            if line.startswith(emoji):
                raw[key] = line[len(emoji):].strip()
                logger.debug("CHANNEL_IMPORT | matched field %r = %r", key, raw[key])
                break
        else:
            logger.debug("CHANNEL_IMPORT | unmatched line: %r", line)

    logger.debug("CHANNEL_IMPORT | detected emoji fields: %s", list(raw.keys()))

    if "city" not in raw:
        logger.warning(
            "CHANNEL_IMPORT | REJECTED — missing city (📍 prefix not found). "
            "Detected fields: %s",
            list(raw.keys()),
        )
        return None
    if "price" not in raw:
        logger.warning(
            "CHANNEL_IMPORT | REJECTED — missing price (💰 prefix not found). "
            "Detected fields: %s",
            list(raw.keys()),
        )
        return None

    city = raw["city"].strip()
    area_type = CITY_AREA_MAP.get(city, "")
    logger.debug("CHANNEL_IMPORT | city=%r  area_type=%r", city, area_type)

    price = _parse_price(raw["price"])
    if price is None:
        logger.warning(
            "CHANNEL_IMPORT | REJECTED — price field present (%r) but failed to parse "
            "(expected format: '۲.۵ میلیارد' / '800 میلیون' / raw number)",
            raw["price"],
        )
        return None

    logger.debug("CHANNEL_IMPORT | price parsed OK: %s toman", price)

    # Villa code
    code_raw = raw.get("code", "AUTO").strip()
    villa_code: str | None = (
        None if (not code_raw or code_raw.upper() == "AUTO") else code_raw
    )

    # Features
    feature_flags: dict[str, int] = {
        "has_pool": 0, "has_jacuzzi": 0,
        "has_roof_garden": 0, "has_parking": 0, "has_storage": 0,
    }
    if "features" in raw:
        for keyword, col in FEATURE_MAP.items():
            if keyword in raw["features"]:
                feature_flags[col] = 1

    return {
        "villa_code":     villa_code,       # None → auto-generate
        "city":           city,
        "area_type":      area_type,
        "price":          price,
        "land_size":      _parse_float(raw.get("land", "")),
        "building_size":  _parse_float(raw.get("building", "")),
        "bedrooms":       _parse_int(raw.get("bedrooms", "")),
        "is_townhouse":   0,
        "document_type":  raw.get("document", ""),
        "description":    raw.get("description", ""),
        "latitude":       None,
        "longitude":      None,
        "photos":         [],               # filled in later
        "video":          None,
        **feature_flags,
    }


# ── Media group buffer ─────────────────────────────────────────────────────────
# Keyed by media_group_id.  Holds the caption text and all photo file_ids
# until the group is complete (detected by a short timeout).

_buffer: dict[str, dict] = {}
_TIMEOUT = 2.5  # seconds to wait for remaining group photos


async def _flush_group(group_id: str, bot: Bot) -> None:
    """Called after the timeout; processes the buffered media group."""
    await asyncio.sleep(_TIMEOUT)
    entry = _buffer.pop(group_id, None)
    if entry is None:
        return
    caption = entry.get("caption", "")
    photo_ids: list[str] = entry.get("photo_ids", [])
    await _save_villa(bot, caption, photo_ids)


# ── Core save logic ────────────────────────────────────────────────────────────

async def _save_villa(bot: Bot, text: str, photo_ids: list[str]) -> None:
    """Parse text, resolve villa code, insert to DB, notify admin."""
    if not text.strip():
        return

    data = parse_villa_post(text)
    if data is None:
        await bot.send_message(
            ADMIN_ID,
            "⚠️ پست کانال دریافت شد اما فرمت صحیح نیست.\n"
            "مطمئن شو که فیلدهای 📍 شهر و 💰 قیمت وجود دارند.",
        )
        return

    # Auto-generate villa code if not provided or duplicate
    if data["villa_code"] is None or get_villa_by_code(data["villa_code"]):
        data["villa_code"] = get_next_villa_code()

    data["photos"] = photo_ids

    try:
        villa_id = insert_villa(data)
    except Exception as exc:
        logger.exception("channel_importer: DB insert failed")
        await bot.send_message(
            ADMIN_ID,
            f"❌ خطا در ذخیره ویلا از کانال:\n<code>{exc}</code>",
            parse_mode="HTML",
        )
        return

    price_b = data["price"] / 1_000_000_000
    photos_count = len(photo_ids)
    await bot.send_message(
        ADMIN_ID,
        f"✅ ویلا از کانال ذخیره شد\n\n"
        f"🏷 کد: <b>{data['villa_code']}</b>\n"
        f"📍 شهر: {data['city']}  |  {data['area_type']}\n"
        f"💰 قیمت: {price_b:.2f} میلیارد\n"
        f"🖼 تعداد عکس: {photos_count}",
        parse_mode="HTML",
    )
    logger.info(
        "channel_importer: saved villa %s (id=%s, photos=%s)",
        data["villa_code"], villa_id, photos_count,
    )


# ── PTB handler ────────────────────────────────────────────────────────────────

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post
    if post is None:
        return

    # If CHANNEL_ID is configured, ignore posts from other channels
    if CHANNEL_ID and post.chat.id != CHANNEL_ID:
        return

    # ── Case 1: plain text post ────────────────────────────────────────────────
    if post.text and not post.photo:
        await _save_villa(context.bot, post.text, [])
        return

    # ── Case 2: photo(s) ──────────────────────────────────────────────────────
    if post.photo:
        best = post.photo[-1].file_id  # highest resolution

        # Single photo (no media group)
        if not post.media_group_id:
            caption = post.caption or ""
            await _save_villa(context.bot, caption, [best])
            return

        # Part of a media group — buffer it
        gid = post.media_group_id
        caption = post.caption or ""  # only first photo has caption

        if gid not in _buffer:
            _buffer[gid] = {"caption": caption, "photo_ids": [], "task": None}
        elif caption:
            # Overwrite only if this message carries a caption (first in group)
            _buffer[gid]["caption"] = caption

        _buffer[gid]["photo_ids"].append(best)

        # Cancel previous flush task and schedule a new one
        old_task: asyncio.Task | None = _buffer[gid].get("task")
        if old_task and not old_task.done():
            old_task.cancel()
        _buffer[gid]["task"] = asyncio.create_task(
            _flush_group(gid, context.bot)
        )


def channel_import_handler() -> MessageHandler:
    """Return the MessageHandler that should be added to the Application."""
    return MessageHandler(
        filters.UpdateType.CHANNEL_POSTS,
        handle_channel_post,
    )
