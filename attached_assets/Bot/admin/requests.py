from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import (
    get_requests,
    get_requests_count,
    mark_request_contacted,
    delete_request,
)
from utils import price_category

PAGE_SIZE = 1   # one request per page for clarity on mobile

REQUEST_TYPE_LABELS: dict[str, str] = {
    "visit":        "☎️ درخواست بازدید",
    "consultation": "💬 مشاوره",
}

STATUS_LABELS: dict[str, str] = {
    "pending":   "⏳ در انتظار تماس",
    "contacted": "✅ تماس گرفته شد",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_date(dt_str: str) -> str:
    if not dt_str:
        return "—"
    try:
        dt = datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y/%m/%d   ساعت %H:%M")
    except Exception:
        return dt_str


def _build_card(req: dict, page: int, total: int) -> str:
    req_type  = REQUEST_TYPE_LABELS.get(req.get("request_type") or "visit", "—")
    status    = STATUS_LABELS.get(req.get("status") or "pending", "—")
    area      = req.get("area_type") or "—"
    cat       = price_category(req.get("price")) if req.get("price") is not None else "—"

    contacted_mark = "   ✅" if req.get("status") == "contacted" else ""

    return (
        f"📋 *درخواست‌ها*{contacted_mark}   _({page + 1} از {total})_\n"
        f"\n"
        f"🆔 شماره: `#{req['id']}`\n"
        f"📅 تاریخ: {_fmt_date(req.get('created_at', ''))}\n"
        f"🔖 نوع: {req_type}\n"
        f"📌 وضعیت: {status}\n"
        f"\n"
        f"👤 نام: {req.get('name', '—')}\n"
        f"📞 شماره: `{req.get('phone', '—')}`\n"
        f"\n"
        f"🏡 ویلا: `{req.get('villa_code', '—')}`\n"
        f"🌊 منطقه: {area}\n"
        f"💰 دسته‌بندی: {cat}"
    )


def _build_kb(req: dict, page: int, total: int) -> InlineKeyboardMarkup:
    req_id  = req["id"]
    status  = req.get("status") or "pending"

    # Contact button changes label once already marked
    if status == "contacted":
        contact_btn = InlineKeyboardButton(
            "☑️ تماس شده",
            callback_data=f"req_contact_{req_id}_{page}",
        )
    else:
        contact_btn = InlineKeyboardButton(
            "✅ تماس گرفتم",
            callback_data=f"req_contact_{req_id}_{page}",
        )

    delete_btn = InlineKeyboardButton(
        "🗑 حذف",
        callback_data=f"req_del_{req_id}_{page}",
    )

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"req_page_{page - 1}"))
    if page < total - 1:
        nav_row.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"req_page_{page + 1}"))

    rows = [[contact_btn, delete_btn]]
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(rows)


# ── Core render ────────────────────────────────────────────────────────────────

async def _render_page(
    chat_id: int,
    message_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
    page: int,
) -> None:
    total = get_requests_count()

    if total == 0:
        text = "📋 هیچ درخواستی ثبت نشده است."
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=text
                )
            except Exception:
                pass
        else:
            await context.bot.send_message(chat_id=chat_id, text=text)
        return

    page = max(0, min(page, total - 1))
    rows = get_requests(page=page, page_size=PAGE_SIZE)
    if not rows:
        return

    req  = rows[0]
    text = _build_card(req, page, total)
    kb   = _build_kb(req, page, total)

    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=kb,
            )
        except Exception:
            pass
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=kb,
        )


# ── Entry from ReplyKeyboard ───────────────────────────────────────────────────

async def handle_requests_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    await _render_page(
        chat_id=update.effective_chat.id,
        message_id=None,
        context=context,
        page=0,
    )


# ── Inline callbacks ───────────────────────────────────────────────────────────

async def cb_req_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    # callback data: req_page_{page}
    page = int(query.data.split("_")[-1])
    await _render_page(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        context=context,
        page=page,
    )


async def cb_req_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("دسترسی مجاز نیست.", show_alert=True)
        return
    # callback data: req_contact_{req_id}_{page}
    parts  = query.data.split("_")
    req_id = int(parts[2])
    page   = int(parts[3])

    mark_request_contacted(req_id)
    await query.answer("✅ وضعیت به 'تماس گرفته شد' تغییر یافت.")
    await _render_page(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        context=context,
        page=page,
    )


async def cb_req_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("دسترسی مجاز نیست.", show_alert=True)
        return
    # callback data: req_del_{req_id}_{page}
    parts  = query.data.split("_")
    req_id = int(parts[2])
    page   = int(parts[3])

    delete_request(req_id)
    await query.answer("🗑 درخواست حذف شد.")

    total_after = get_requests_count()
    if total_after == 0:
        try:
            await query.message.edit_text("📋 هیچ درخواستی باقی نمانده است.")
        except Exception:
            pass
        return

    new_page = min(page, total_after - 1)
    await _render_page(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        context=context,
        page=new_page,
    )
