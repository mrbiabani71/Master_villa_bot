"""
Admin Villa Management panel — 🏡 مدیریت ویلاها

Lets the admin search across ALL villas (every status), view a summary card
for each result, and take one of four actions:

  ✏️ Edit       — end this flow, prompt admin to use «✏️ ویرایش ویلا»
  🗑 Delete      — ask for confirmation → permanently delete from DB
  🚫 Deactivate  — set status=inactive (hidden from customer search)
  📋 Full details — send all fields + all photos in pages of ≤10

Search criteria
  🔢 by villa code  — partial match, case-insensitive
  🏙 by city        — partial match
  💰 by max price   — inclusive upper bound in billion Tomans
  📋 all villas     — no filter

States
  MV_SEARCH (34)        — search type keyboard + value input + result card callbacks
  MV_CONFIRM_DELETE (35) — waiting for confirm/cancel inline button after 🗑
"""
from __future__ import annotations

import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_ID
from keyboards import admin_panel_keyboard, get_main_keyboard
from pg_villas import admin_search_villas, delete_villa, get_villa_by_id, set_villa_status
from states import MV_CONFIRM_DELETE, MV_SEARCH

logger = logging.getLogger(__name__)

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

_PAGE_SIZE = 8


def _to_latin(text: str) -> str:
    return text.translate(_DIGIT_TABLE)


def _is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID


# ── Keyboards ─────────────────────────────────────────────────────────────────

def _search_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["🔢 جستجو با کد", "🏙 جستجو با شهر"],
            ["💰 جستجو با قیمت", "📋 همه ویلاها"],
            ["⬅️ بازگشت"],
        ],
        resize_keyboard=True,
    )


# ── Status label map ──────────────────────────────────────────────────────────

_STATUS_FA: dict[str, str] = {
    "draft":     "پیش‌نویس ✏️",
    "published": "منتشر ✅",
    "sold":      "فروخته شده 💰",
    "archived":  "آرشیو 📦",
    "inactive":  "غیرفعال 🚫",
}


def _status_fa(status: str | None) -> str:
    return _STATUS_FA.get(status or "", status or "—")


# ── Results display ───────────────────────────────────────────────────────────

def _results_markup(results: list[dict], page: int) -> InlineKeyboardMarkup:
    start = page * _PAGE_SIZE
    end   = min(start + _PAGE_SIZE, len(results))

    buttons: list[list[InlineKeyboardButton]] = []
    for v in results[start:end]:
        code    = v.get("villa_code") or "?"
        city    = v.get("city") or "—"
        price   = v.get("price")
        p_str   = f"{price / 1_000_000_000:.1f}B" if price else "—"
        status  = _status_fa(v.get("status"))
        label   = f"{code}  {city}  {p_str}  {status}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"mv_select_{v['id']}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"mv_page_{page - 1}"))
    if end < len(results):
        nav.append(InlineKeyboardButton("▶️ بعدی", callback_data=f"mv_page_{page + 1}"))
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(buttons)


async def _send_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    results: list[dict],
    page: int = 0,
) -> None:
    context.user_data["mv_results"] = results
    context.user_data["mv_page"]    = page

    if not results:
        await update.message.reply_text(
            "❌ ویلایی یافت نشد.\n\nمجدداً جستجو کنید:",
            reply_markup=_search_kb(),
        )
        return

    total = len(results)
    start = page * _PAGE_SIZE
    end   = min(start + _PAGE_SIZE, total)

    await update.message.reply_text(
        f"🏡 *{total} ویلا یافت شد* — صفحه {page + 1} از {((total - 1) // _PAGE_SIZE) + 1}\n\n"
        "یک ویلا انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_results_markup(results, page),
    )
    context.user_data["mv_step"] = "type"


# ── Entry ─────────────────────────────────────────────────────────────────────

async def start_manage_villas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return ConversationHandler.END

    context.user_data.pop("mv_step", None)
    context.user_data.pop("mv_search_type", None)
    context.user_data.pop("mv_results", None)
    context.user_data.pop("mv_page", None)
    context.user_data.pop("mv_del_villa_id", None)

    context.user_data["mv_step"] = "type"

    await update.message.reply_text(
        "🏡 *مدیریت ویلاها*\n\n"
        "نوع جستجو را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_search_kb(),
    )
    return MV_SEARCH


# ── MV_SEARCH: text handler ───────────────────────────────────────────────────

async def handle_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    step = context.user_data.get("mv_step", "type")

    # ── Back ──────────────────────────────────────────────────────────────────
    if text == "⬅️ بازگشت":
        context.user_data.clear()
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel_keyboard)
        return ConversationHandler.END

    # ── Search type selection ─────────────────────────────────────────────────
    if step == "type":
        if text == "📋 همه ویلاها":
            loading = await update.message.reply_text(
                "🔍 در حال بارگذاری…", reply_markup=ReplyKeyboardRemove()
            )
            results = admin_search_villas()
            await loading.delete()
            await _send_results(update, context, results)
            return MV_SEARCH

        if text in ("🔢 جستجو با کد", "🏙 جستجو با شهر", "💰 جستجو با قیمت"):
            context.user_data["mv_search_type"] = text
            context.user_data["mv_step"] = "value"
            prompts = {
                "🔢 جستجو با کد":    "کد ویلا را وارد کنید (مثلاً MV-1234 یا فقط عدد):",
                "🏙 جستجو با شهر":   "نام شهر را وارد کنید:",
                "💰 جستجو با قیمت":  "حداکثر قیمت را به میلیارد تومان وارد کنید (مثلاً 10):",
            }
            await update.message.reply_text(
                prompts[text], reply_markup=ReplyKeyboardRemove()
            )
            return MV_SEARCH

        await update.message.reply_text(
            "لطفاً از دکمه‌های منو استفاده کنید:", reply_markup=_search_kb()
        )
        return MV_SEARCH

    # ── Search value input ────────────────────────────────────────────────────
    if step == "value":
        search_type = context.user_data.get("mv_search_type", "")

        if search_type == "🔢 جستجو با کد":
            raw = _to_latin(text).upper().strip()
            if raw.isdigit():
                raw = f"MV-{int(raw):04d}"
            loading = await update.message.reply_text("🔍 در حال جستجو…")
            results = admin_search_villas(code=raw)
            await loading.delete()

        elif search_type == "🏙 جستجو با شهر":
            loading = await update.message.reply_text("🔍 در حال جستجو…")
            results = admin_search_villas(city=text)
            await loading.delete()

        elif search_type == "💰 جستجو با قیمت":
            raw_num = _to_latin(text).replace(",", "").replace("،", "").strip()
            try:
                max_price = float(raw_num) * 1_000_000_000
            except ValueError:
                await update.message.reply_text(
                    "⚠️ لطفاً یک عدد معتبر وارد کنید (مثلاً 10 برای ۱۰ میلیارد):"
                )
                return MV_SEARCH
            loading = await update.message.reply_text("🔍 در حال جستجو…")
            results = admin_search_villas(max_price=max_price)
            await loading.delete()

        else:
            results = admin_search_villas()

        context.user_data["mv_step"] = "type"
        await _send_results(update, context, results)
        return MV_SEARCH

    # Fallback: go back to type selection
    await update.message.reply_text("نوع جستجو را انتخاب کنید:", reply_markup=_search_kb())
    context.user_data["mv_step"] = "type"
    return MV_SEARCH


# ── MV_SEARCH: pagination callback ────────────────────────────────────────────

async def cb_mv_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    page    = int(query.data.removeprefix("mv_page_"))
    results: list[dict] = context.user_data.get("mv_results", [])

    if not results:
        await query.edit_message_text("❌ نتایج منقضی شده. مجدداً جستجو کنید.")
        return MV_SEARCH

    total = len(results)
    context.user_data["mv_page"] = page

    await query.edit_message_text(
        f"🏡 *{total} ویلا یافت شد* — صفحه {page + 1} از {((total - 1) // _PAGE_SIZE) + 1}\n\n"
        "یک ویلا انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_results_markup(results, page),
    )
    return MV_SEARCH


# ── MV_SEARCH: villa selected → show summary card ─────────────────────────────

_REPUBLISHABLE = {"inactive", "draft"}


def _card_keyboard(villa_id: int, status: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("✏️ ویرایش",       callback_data=f"mv_edit_{villa_id}"),
            InlineKeyboardButton("📋 جزئیات کامل",  callback_data=f"mv_details_{villa_id}"),
        ],
        [
            InlineKeyboardButton("🚫 غیرفعال کردن", callback_data=f"mv_deact_{villa_id}"),
            InlineKeyboardButton("🗑 حذف",           callback_data=f"mv_del_{villa_id}"),
        ],
    ]
    if status in _REPUBLISHABLE:
        rows.append([
            InlineKeyboardButton("♻️ بازنشر", callback_data=f"mv_repost_ask_{villa_id}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ بازگشت به نتایج", callback_data="mv_back_results")])
    return InlineKeyboardMarkup(rows)


def _build_card(v: dict, photos: list[str]) -> str:
    price   = v.get("price")
    p_str   = f"{price / 1_000_000_000:.2f} میلیارد" if price else "—"
    return (
        f"🏡 *{v.get('villa_code')}*\n\n"
        f"📍 شهر: {v.get('city') or '—'}\n"
        f"💰 قیمت: {p_str}\n"
        f"🖼 تعداد عکس: {len(photos)}\n"
        f"📊 وضعیت: {_status_fa(v.get('status'))}"
    )


async def cb_mv_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_select_"))
    villa    = get_villa_by_id(villa_id)

    if not villa:
        await query.edit_message_text("❌ ویلا یافت نشد.")
        return MV_SEARCH

    photos = [p.strip() for p in (villa.get("photos") or "").split(",") if p.strip()]
    context.user_data["mv_current_villa_id"] = villa_id

    await query.edit_message_text(
        _build_card(villa, photos),
        parse_mode="Markdown",
        reply_markup=_card_keyboard(villa_id, villa.get("status")),
    )
    return MV_SEARCH


# ── MV_SEARCH: back to results list ──────────────────────────────────────────

async def cb_mv_back_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query   = update.callback_query
    await query.answer()

    results: list[dict] = context.user_data.get("mv_results", [])
    page    = context.user_data.get("mv_page", 0)

    if not results:
        await query.edit_message_text("جستجوی جدید انجام دهید.")
        await context.bot.send_message(
            update.effective_user.id,
            "نوع جستجو را انتخاب کنید:",
            reply_markup=_search_kb(),
        )
        return MV_SEARCH

    total = len(results)
    await query.edit_message_text(
        f"🏡 *{total} ویلا یافت شد* — صفحه {page + 1} از {((total - 1) // _PAGE_SIZE) + 1}\n\n"
        "یک ویلا انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=_results_markup(results, page),
    )
    return MV_SEARCH


# ── MV_SEARCH: ✏️ Edit ────────────────────────────────────────────────────────

async def cb_mv_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_edit_"))
    villa    = get_villa_by_id(villa_id)
    code     = (villa or {}).get("villa_code") or str(villa_id)

    await query.edit_message_text(
        f"✏️ برای ویرایش ویلا *{code}* از گزینه «✏️ ویرایش ویلا» در منوی مدیریت استفاده کنید.\n\n"
        f"کد ویلا: `{code}`",
        parse_mode="Markdown",
    )
    await context.bot.send_message(
        update.effective_user.id,
        "👑 پنل مدیریت",
        reply_markup=admin_panel_keyboard,
    )
    context.user_data.clear()
    return ConversationHandler.END


# ── MV_SEARCH: 📋 Full details ────────────────────────────────────────────────

async def cb_mv_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_details_"))
    villa    = get_villa_by_id(villa_id)

    if not villa:
        await query.answer("❌ ویلا یافت نشد", show_alert=True)
        return MV_SEARCH

    photos = [p.strip() for p in (villa.get("photos") or "").split(",") if p.strip()]

    def yn(val: object) -> str:
        return "✅" if val else "❌"

    price   = villa.get("price")
    p_str   = f"{price / 1_000_000_000:.2f} میلیارد" if price else "—"

    details = (
        f"📋 *جزئیات کامل ویلا*\n\n"
        f"🏷 کد: `{villa.get('villa_code')}`\n"
        f"📍 شهر: {villa.get('city') or '—'}\n"
        f"🌊 نوع منطقه: {villa.get('area_type') or '—'}\n"
        f"💰 قیمت: {p_str}\n"
        f"📐 متراژ زمین: {villa.get('land_size') or '—'} م²\n"
        f"🏠 متراژ بنا: {villa.get('building_size') or '—'} م²\n"
        f"🛏 اتاق‌خواب: {villa.get('bedrooms') or '—'}\n"
        f"🛏 مستر: {villa.get('master_bedrooms') or '—'}\n"
        f"🏊 استخر: {yn(villa.get('has_pool'))}\n"
        f"🛁 جکوزی: {yn(villa.get('has_jacuzzi'))}\n"
        f"🌿 روف گاردن: {yn(villa.get('has_roof_garden'))}\n"
        f"🚗 پارکینگ: {yn(villa.get('has_parking'))}\n"
        f"📦 انباری: {yn(villa.get('has_storage'))}\n"
        f"📄 سند: {villa.get('document_type') or '—'}\n"
        f"📊 وضعیت: {_status_fa(villa.get('status'))}\n"
        f"🖼 تعداد عکس: {len(photos)}\n"
        f"📝 توضیحات:\n{villa.get('description') or '—'}"
    )

    uid = update.effective_user.id
    await context.bot.send_message(uid, details, parse_mode="Markdown")

    if photos:
        await context.bot.send_message(uid, f"🖼 عکس‌های ویلا ({len(photos)} عکس):")
        for i in range(0, len(photos), 10):
            batch = photos[i : i + 10]
            if len(batch) == 1:
                await context.bot.send_photo(uid, batch[0])
            else:
                media = [InputMediaPhoto(fid) for fid in batch]
                await context.bot.send_media_group(uid, media)

    logger.info(
        "manage_villas | details sent for villa_id=%s code=%s photos=%d",
        villa_id, villa.get("villa_code"), len(photos),
    )
    return MV_SEARCH


# ── MV_SEARCH: 🚫 Deactivate ─────────────────────────────────────────────────

async def cb_mv_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_deact_"))
    villa    = get_villa_by_id(villa_id)
    code     = (villa or {}).get("villa_code") or str(villa_id)

    ok = set_villa_status(villa_id, "inactive")
    if ok:
        logger.info("manage_villas | deactivated villa_id=%s code=%s", villa_id, code)
        await query.edit_message_text(
            f"🚫 *ویلا غیرفعال شد*\n\n"
            f"🏷 کد: {code}\n\n"
            "این ویلا از نتایج جستجوی مشتریان پنهان است و رکورد آن در پایگاه داده حفظ می‌شود.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ بازگشت به نتایج", callback_data="mv_back_results")],
            ]),
        )
    else:
        await query.edit_message_text(
            "❌ خطا در غیرفعال کردن ویلا. لطفاً دوباره تلاش کنید.",
            reply_markup=_card_keyboard(villa_id),
        )

    return MV_SEARCH


# ── MV_SEARCH: 🗑 Delete → ask confirmation → MV_CONFIRM_DELETE ───────────────

async def cb_mv_delete_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_del_"))
    villa    = get_villa_by_id(villa_id)
    code     = (villa or {}).get("villa_code") or str(villa_id)

    context.user_data["mv_del_villa_id"] = villa_id

    await query.edit_message_text(
        f"⚠️ *تأیید حذف ویلا*\n\n"
        f"🏷 کد: *{code}*\n\n"
        "این عملیات غیرقابل بازگشت است.\n"
        "ویلا به طور دائمی از پایگاه داده حذف خواهد شد.\n\n"
        "آیا مطمئن هستید؟",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"mv_confirmdel_{villa_id}"),
                InlineKeyboardButton("❌ انصراف",        callback_data="mv_canceldel"),
            ],
        ]),
    )
    return MV_CONFIRM_DELETE


# ── MV_CONFIRM_DELETE: confirmed ──────────────────────────────────────────────

async def cb_mv_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_confirmdel_"))
    villa    = get_villa_by_id(villa_id)
    code     = (villa or {}).get("villa_code") or str(villa_id)

    ok = delete_villa(villa_id)
    if ok:
        logger.info("manage_villas | permanently deleted villa_id=%s code=%s", villa_id, code)

        # Remove the deleted villa from the cached results list so pagination stays consistent
        results: list[dict] = context.user_data.get("mv_results", [])
        context.user_data["mv_results"] = [v for v in results if v.get("id") != villa_id]

        await query.edit_message_text(
            f"🗑 *ویلا {code} حذف شد*\n\n"
            "رکورد ویلا به طور دائمی از پایگاه داده پاک شد.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ بازگشت به نتایج", callback_data="mv_back_results")],
            ]),
        )
    else:
        await query.edit_message_text(
            "❌ خطا در حذف ویلا. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f"mv_confirmdel_{villa_id}"),
                    InlineKeyboardButton("❌ انصراف",      callback_data="mv_canceldel"),
                ],
            ]),
        )

    return MV_SEARCH


# ── MV_CONFIRM_DELETE: cancelled ─────────────────────────────────────────────

async def cb_mv_cancel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = context.user_data.get("mv_del_villa_id")
    context.user_data.pop("mv_del_villa_id", None)

    if villa_id:
        villa  = get_villa_by_id(villa_id)
        photos = [p.strip() for p in (villa or {}).get("photos", "").split(",") if p.strip()]
        await query.edit_message_text(
            _build_card(villa, photos) if villa else "⚠️ ویلا یافت نشد.",
            parse_mode="Markdown",
            reply_markup=_card_keyboard(villa_id, villa.get("status")) if villa else None,
        )
    else:
        await query.edit_message_text("حذف لغو شد.")

    return MV_SEARCH


# ── MV_SEARCH: ♻️ Republish — ask confirmation ────────────────────────────────

async def cb_mv_repost_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_repost_ask_"))
    villa    = get_villa_by_id(villa_id)
    code     = (villa or {}).get("villa_code") or str(villa_id)
    status   = (villa or {}).get("status") or "—"

    if status not in _REPUBLISHABLE:
        await query.answer(
            f"وضعیت فعلی «{_status_fa(status)}» قابل بازنشر نیست.",
            show_alert=True,
        )
        return MV_SEARCH

    await query.edit_message_text(
        f"♻️ *تأیید بازنشر ویلا*\n\n"
        f"🏷 کد: *{code}*\n"
        f"📊 وضعیت فعلی: {_status_fa(status)}\n\n"
        f"وضعیت به *منتشر* تغییر می‌کند و ویلا در نتایج جستجوی مشتریان نمایش داده خواهد شد.\n\n"
        "آیا مطمئن هستید؟",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، بازنشر شود",  callback_data=f"mv_repost_confirm_{villa_id}"),
                InlineKeyboardButton("❌ انصراف",            callback_data=f"mv_repost_cancel_{villa_id}"),
            ],
        ]),
    )
    return MV_SEARCH


# ── MV_SEARCH: ♻️ Republish — confirmed ──────────────────────────────────────

async def cb_mv_repost_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_repost_confirm_"))
    villa    = get_villa_by_id(villa_id)
    code     = (villa or {}).get("villa_code") or str(villa_id)
    old_status = (villa or {}).get("status") or "—"

    if old_status not in _REPUBLISHABLE:
        await query.answer(
            f"وضعیت «{_status_fa(old_status)}» قابل بازنشر نیست.",
            show_alert=True,
        )
        return MV_SEARCH

    ok = set_villa_status(villa_id, "published")
    if ok:
        logger.info(
            "manage_villas | republished villa_id=%s code=%s  %s → published",
            villa_id, code, old_status,
        )
        await query.edit_message_text(
            f"♻️ *ویلا بازنشر شد*\n\n"
            f"🏷 کد: {code}\n"
            f"📊 وضعیت: {_status_fa(old_status)} ← *منتشر ✅*\n\n"
            "این ویلا اکنون در نتایج جستجوی مشتریان نمایش داده می‌شود.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ بازگشت به نتایج", callback_data="mv_back_results")],
            ]),
        )
    else:
        await query.edit_message_text(
            "❌ خطا در بازنشر ویلا. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 تلاش مجدد",  callback_data=f"mv_repost_confirm_{villa_id}"),
                    InlineKeyboardButton("❌ انصراف",       callback_data=f"mv_repost_cancel_{villa_id}"),
                ],
            ]),
        )

    return MV_SEARCH


# ── MV_SEARCH: ♻️ Republish — cancelled ──────────────────────────────────────

async def cb_mv_repost_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    villa_id = int(query.data.removeprefix("mv_repost_cancel_"))
    villa    = get_villa_by_id(villa_id)
    photos   = [p.strip() for p in (villa or {}).get("photos", "").split(",") if p.strip()]

    await query.edit_message_text(
        _build_card(villa, photos) if villa else "⚠️ ویلا یافت نشد.",
        parse_mode="Markdown",
        reply_markup=_card_keyboard(villa_id, (villa or {}).get("status")) if villa else None,
    )
    return MV_SEARCH


# ── Cancel command ────────────────────────────────────────────────────────────

async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ مدیریت ویلاها لغو شد.",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


# ── ConversationHandler factory ───────────────────────────────────────────────

def build_manage_villas_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🏡 مدیریت ویلاها$"), start_manage_villas),
        ],
        states={
            MV_SEARCH: [
                # Inline callbacks — result list
                CallbackQueryHandler(cb_mv_page,         pattern=r"^mv_page_\d+$"),
                CallbackQueryHandler(cb_mv_select,       pattern=r"^mv_select_\d+$"),
                CallbackQueryHandler(cb_mv_back_results, pattern="^mv_back_results$"),
                # Inline callbacks — card actions
                CallbackQueryHandler(cb_mv_edit,       pattern=r"^mv_edit_\d+$"),
                CallbackQueryHandler(cb_mv_details,    pattern=r"^mv_details_\d+$"),
                CallbackQueryHandler(cb_mv_deactivate,   pattern=r"^mv_deact_\d+$"),
                CallbackQueryHandler(cb_mv_delete_ask,   pattern=r"^mv_del_\d+$"),
                CallbackQueryHandler(cb_mv_repost_ask,    pattern=r"^mv_repost_ask_\d+$"),
                CallbackQueryHandler(cb_mv_repost_confirm,pattern=r"^mv_repost_confirm_\d+$"),
                CallbackQueryHandler(cb_mv_repost_cancel, pattern=r"^mv_repost_cancel_\d+$"),
                # Text input (search type + value)
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text),
            ],
            MV_CONFIRM_DELETE: [
                CallbackQueryHandler(cb_mv_confirm_delete, pattern=r"^mv_confirmdel_\d+$"),
                CallbackQueryHandler(cb_mv_cancel_delete,  pattern="^mv_canceldel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            MessageHandler(filters.Regex("^⬅️ بازگشت$"), handle_search_text),
        ],
        per_message=False,
    )
