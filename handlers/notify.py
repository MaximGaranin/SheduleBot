"""Handlers for daily schedule notification subscription.

Logic:
  - /notify or button → toggle subscription on/off
  - APScheduler jobs (registered in bot.py):
      22:00 MSK → send tomorrow's schedule
      08:00 MSK → send today's schedule
"""
import logging
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest

from config import BASE_URL, WEEKDAY_TO_DAY, MAIN_MENU, FACULTIES, STUDY_FORMS
from database import (
    get_profile,
    get_notify_subscribers,
    set_notify_subscription,
    is_notify_subscribed,
)
from fetcher import fetch_page
from parser import parse_schedule_html, filter_day
from utils import send_long

logger = logging.getLogger(__name__)
MSK = pytz.timezone("Europe/Moscow")
DIVIDER = "─" * 28


# ──────────────────────────────────────────────
# Button handler (toggle subscription)
# ──────────────────────────────────────────────

async def toggle_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    profile = get_profile(user_id)

    if not profile:
        await query.answer(
            "⚠️ Сначала настройте профиль (группу) через главное меню.",
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
# Scheduled jobs
# ──────────────────────────────────────────────

async def _send_day_schedule(bot, user_id: int, day_key: str, label: str):
    """Fetch and send schedule for `day_key` ('today'/'tomorrow') to user."""
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

    now = datetime.now(MSK)
    if day_key == "today":
        target_dt = now
    else:  # tomorrow
        target_dt = now + timedelta(days=1)

    weekday   = target_dt.weekday()   # 0=Mon … 5=Sat, 6=Sun
    day_short = WEEKDAY_TO_DAY.get(weekday)

    fac_name = FACULTIES.get(faculty, faculty)
    frm_name = STUDY_FORMS.get(form, form)
    date_str = target_dt.strftime("%d.%m.%Y")

    if day_short is None:
        text = (
            f"🔔 *{label} ({date_str}) — воскресенье*\n"
            f"📚 Группа *{grp}* | {fac_name}\n"
            f"{DIVIDER}\n"
            "🎉 Занятий нет!"
        )
    else:
        day_schedule = filter_day(parse_schedule_html(html), day_short)
        if not day_schedule or day_schedule.strip() == "":
            day_schedule = "Занятий нет (или расписание не найдено)."
        text = (
            f"🔔 *{label} — {day_short} {date_str}*\n"
            f"📚 Группа *{grp}* | {fac_name}\n"
            f"{DIVIDER}\n"
            + day_schedule
        )

    try:
        await send_long_bot(bot, user_id, text)
    except Forbidden:
        logger.info(f"notify: user {user_id} blocked the bot — unsubscribing")
        set_notify_subscription(user_id, False)
    except Exception as e:
        logger.error(f"notify: error sending to {user_id}: {e}")


async def send_long_bot(bot, chat_id: int, text: str):
    """Split long text and send via bot object (not update)."""
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
    """22:00 MSK — send tomorrow's schedule."""
    subscribers = get_notify_subscribers()
    logger.info(f"notify evening job: {len(subscribers)} subscribers")
    for user_id in subscribers:
        await _send_day_schedule(context.bot, user_id, "tomorrow", "Расписание на завтра")


async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    """08:00 MSK — send today's schedule."""
    subscribers = get_notify_subscribers()
    logger.info(f"notify morning job: {len(subscribers)} subscribers")
    for user_id in subscribers:
        await _send_day_schedule(context.bot, user_id, "today", "Расписание на сегодня")
