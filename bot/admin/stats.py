"""
Admin statistics panel — 📊 آمار

Fetches live data from two API endpoints in parallel (via threads because
httpx is used synchronously) and formats a single Farsi message.

Shown data
  • Villa counts  : total / published / inactive / sold / archived
  • By city       : top cities (active villas only)
  • By region type: ساحلی / جنگلی breakdown
  • By price tier : 5 custom tiers
  • Visit requests: total / pending / contacted / visit / consultation
  • Latest import : date of the most-recently channel-imported villa
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from keyboards import admin_panel_keyboard
from pg_stats import get_villa_stats, get_request_stats

logger = logging.getLogger(__name__)


def _fmt_date(iso: str | None) -> str:
    """Convert ISO-8601 UTC string to a human-readable local date."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d  %H:%M UTC")
    except Exception:
        return iso[:10]


def _bar(count: int, total: int, width: int = 10) -> str:
    """Simple ASCII progress bar."""
    if total <= 0:
        return "░" * width
    filled = round(count / total * width)
    return "█" * filled + "░" * (width - filled)


def _build_message(vs: dict, rs: dict | None) -> str:
    sep = "━━━━━━━━━━━━━━━━━━"

    # ── Villa counts ──────────────────────────────────────────────────────────
    total     = vs.get("total", 0)
    published = vs.get("published", 0)
    inactive  = vs.get("inactive", 0)
    sold      = vs.get("sold", 0)
    archived  = vs.get("archived", 0)
    draft     = vs.get("draft", 0)

    lines = [
        "📊 *آمار لحظه‌ای پایگاه داده*",
        "",
        f"🏡 *ویلاها*",
        sep,
        f"📦 مجموع:          *{total}*",
        f"✅ منتشر:          *{published}*",
        f"🚫 غیرفعال:        *{inactive}*",
        f"💰 فروخته شده:     *{sold}*",
        f"📦 آرشیو:          *{archived}*",
        f"✏️ پیش‌نویس:       *{draft}*",
    ]

    # ── By city ───────────────────────────────────────────────────────────────
    by_city: list[dict] = vs.get("by_city", [])
    if by_city:
        active_total = sum(int(c.get("count", 0)) for c in by_city)
        lines += ["", "📍 *بر اساس شهر*", sep]
        for entry in by_city[:10]:  # cap at 10 cities
            city  = entry.get("city") or "—"
            count = int(entry.get("count", 0))
            bar   = _bar(count, active_total, width=8)
            lines.append(f"{bar}  {city}: *{count}*")

    # ── By area type ──────────────────────────────────────────────────────────
    by_area: list[dict] = vs.get("by_area_type", [])
    if by_area:
        area_total = sum(int(e.get("count", 0)) for e in by_area)
        lines += ["", "🌊 *بر اساس نوع منطقه*", sep]
        labels = {"coastal": "ساحلی 🌊", "forest": "جنگلی 🌳"}
        for entry in by_area:
            atype = entry.get("area_type") or "—"
            count = int(entry.get("count", 0))
            bar   = _bar(count, area_total, width=8)
            label = labels.get(atype, atype)
            lines.append(f"{bar}  {label}: *{count}*")

    # ── By price tier ─────────────────────────────────────────────────────────
    by_tier: list[dict] = vs.get("by_price_tier", [])
    if by_tier:
        tier_total = sum(int(e.get("count", 0)) for e in by_tier)
        lines += ["", "💰 *بر اساس قیمت*", sep]
        for entry in by_tier:
            tier  = entry.get("tier") or "—"
            count = int(entry.get("count", 0))
            bar   = _bar(count, tier_total, width=8)
            lines.append(f"{bar}  {tier}: *{count}*")

    # ── Visit requests ────────────────────────────────────────────────────────
    if rs:
        req_total   = rs.get("total", 0)
        req_pending = rs.get("pending", 0)
        req_contact = rs.get("contacted", 0)
        req_visit   = rs.get("visit_count", 0)
        req_consult = rs.get("consultation_count", 0)

        lines += [
            "",
            "📩 *درخواست‌ها*",
            sep,
            f"📬 مجموع:          *{req_total}*",
            f"⏳ در انتظار:      *{req_pending}*",
            f"✅ تماس گرفته:     *{req_contact}*",
            f"🏠 بازدید:         *{req_visit}*",
            f"💬 مشاوره:         *{req_consult}*",
        ]

    # ── Latest import ─────────────────────────────────────────────────────────
    latest = vs.get("latest_import")
    lines += [
        "",
        "📅 *آخرین ایمپورت از کانال*",
        sep,
        f"🕐 {_fmt_date(latest)}",
    ]

    return "\n".join(lines)


async def handle_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("شما دسترسی به این بخش ندارید.")
        return

    loading = await update.message.reply_text("📊 در حال بارگذاری آمار…")

    # Fetch both endpoints concurrently using asyncio threads (httpx is sync)
    loop = asyncio.get_running_loop()
    vs_future = loop.run_in_executor(None, get_villa_stats)
    rs_future = loop.run_in_executor(None, get_request_stats)
    villa_stats, req_stats = await asyncio.gather(vs_future, rs_future)

    await loading.delete()

    if villa_stats is None:
        await update.message.reply_text(
            "❌ خطا در دریافت آمار. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_panel_keyboard,
        )
        return

    try:
        msg = _build_message(villa_stats, req_stats)
    except Exception as exc:
        logger.exception("stats | _build_message failed: %s", exc)
        await update.message.reply_text(
            f"❌ خطا در پردازش آمار:\n<code>{exc}</code>",
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard,
        )
        return

    logger.info(
        "stats | total=%s published=%s inactive=%s sold=%s archived=%s requests=%s",
        villa_stats.get("total"), villa_stats.get("published"),
        villa_stats.get("inactive"), villa_stats.get("sold"),
        villa_stats.get("archived"),
        req_stats.get("total") if req_stats else "N/A",
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard,
    )
