"""Handlers for daily schedule notification subscription.

Logic:
  - button toggle_notify → toggle subscription on/off
  - APScheduler jobs (registered in bot.py):
      22:00 local (TIMEZONE) → send tomorrow's schedule
      08:00 local (TIMEZONE) → send today's schedule
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden

from config import BASE_URL, WEEKDAY_TO_DAY, MAIN_MENU, FACULTIES, STUDY_FORMS, TIMEZONE
from database import (
    get_profile,
    get_notify_subscribers,
    set_notify_subscription,
    is_notify_subscribed,
)
from fetcher import fetch_page
from parser import parse_schedule_html

logger = logging.getLogger(__name__)
TZ = ZoneInfo(TIMEZONE)
DIVIDER = "─" * 28


# ──────────────────────────────────────────────
async def toggle_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    profile = get_profile(user_id)

    if not profile:
        await query.answer(
            "⚠️ Сначала настройте профиль через главное меню.",
            show_alert=True,
        )
        return MAIN_MENU

    currently = is_notify_subscribed(user_id)
    new_state  = not currently
    set_notify_subscription(user_id, new_state)

    if new_state:
        text = (
            "🔔 *Уведомления включены!*\n\n"
            "Я буду присылать:\n"
            "• В *22:00* — расписание на *завтра*\n"
            "• В *08:00* — расписание на *сегодня*\n\n"
            f"⏰ Время: *{TIMEZONE}*\n"
            "Чтобы отключить — нажмите кнопку снова."
        )
    else:
        text = "🔕 *Уведомления отключены.*"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")
        ]])
    )
    return MAIN_MENU


# ──────────────────────────────────────────────
async def _send_day_schedule(bot, user_id: int, day_offset: int, label: str):
    """Fetch and send schedule for today+day_offset to user."""
    profile = get_profile(user_id)
    if not profile:
        return

    faculty = profile["faculty"]
    form    = profile["form"]
    grp     = profile["grp"]
    url     = f"{BASE_URL}/schedule/{faculty}/{form}/{grp}"

    html = await fetch_page(url, use_cache=False)
    if not html:
        logger.warning(f"notify: failed to fetch schedule for user {user_id}")
        return

    target_dt = datetime.now(TZ) + timedelta(days=day_offset)
    weekday   = target_dt.weekday()   # 0=Mon … 5=Sat, 6=Sun
    day_short = WEEKDAY_TO_DAY.get(weekday)
    fac_name  = FACULTIES.get(faculty, faculty)
    date_str  = target_dt.strftime("%d.%m.%Y")

    if day_short is None:
        text = (
            f"🔔 *{label} ({date_str}) — воскресенье*\n"
            f"📚 Группа *{grp}* | {fac_name}\n"
            f"{DIVIDER}\n"
            "🎉 Занятий нет!"
        )
    else:
        day_text = parse_schedule_html(html, only_day=day_short)
        text = (
            f"🔔 *{label} — {day_short} {date_str}*\n"
            f"📚 Группа *{grp}* | {fac_name}\n"
            f"{DIVIDER}\n"
            + day_text
        )

    try:
        await _send_long_bot(bot, user_id, text)
    except Forbidden:
        logger.info(f"notify: user {user_id} blocked the bot — unsubscribing")
        set_notify_subscription(user_id, False)
    except Exception as e:
        logger.error(f"notify: error sending to {user_id}: {e}")


async def _send_long_bot(bot, chat_id: int, text: str):
    MAX = 4000
    parts = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    for part in parts:
        await bot.send_message(
            chat_id=chat_id,
            text=part,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )


async def job_evening(context: ContextTypes.DEFAULT_TYPE):
    """22:00 local — send tomorrow's schedule."""
    subscribers = get_notify_subscribers()
    logger.info(f"notify evening job: {len(subscribers)} subscribers")
    for user_id in subscribers:
        await _send_day_schedule(context.bot, user_id, day_offset=1, label="Расписание на завтра")


async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    """08:00 local — send today's schedule."""
    subscribers = get_notify_subscribers()
    logger.info(f"notify morning job: {len(subscribers)} subscribers")
    for user_id in subscribers:
        await _send_day_schedule(context.bot, user_id, day_offset=0, label="Расписание на сегодня")
