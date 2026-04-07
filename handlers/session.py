"""Handlers for exam/session schedule.

Routes:
  my_session        — session schedule for current user's profile group
  session_fac_*     — choose faculty (for searching any group's session)
  session_form_*    — choose study form
  session_grp       — enter group number, then show session
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import BASE_URL, FACULTIES, STUDY_FORMS, MAIN_MENU
from database import get_profile
from fetcher import fetch_page
from parser import parse_session_html
from keyboards import faculty_keyboard, form_keyboard

logger = logging.getLogger(__name__)

DIVIDER = "─" * 28


# ── Сессия текущего пользователя ─────────────────────────────────────────────
async def show_my_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    profile = get_profile(user_id)

    if not profile:
        await query.edit_message_text(
            "⚠️ Профиль не настроен. Сначала выберите факультет и группу.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👤 Настроить профиль", callback_data="setup_profile"),
                InlineKeyboardButton("🏠 Главное меню",      callback_data="back_main"),
            ]]),
        )
        return MAIN_MENU

    faculty = profile["faculty"]
    form    = profile["form"]
    grp     = profile["grp"]
    url     = f"{BASE_URL}/schedule/{faculty}/{form}/{grp}/session"

    await query.edit_message_text("⏳ Загружаю расписание сессии…")
    html = await fetch_page(url, use_cache=True, ttl=3600)

    if not html:
        await query.edit_message_text(
            "❌ Не удалось загрузить данные. Попробуйте позже.",
            reply_markup=_back_kb(),
        )
        return MAIN_MENU

    fac_name = FACULTIES.get(faculty, faculty)
    header   = f"📝 *Сессия — группа {grp}* | {fac_name}\n{DIVIDER}\n"
    text     = header + parse_session_html(html)

    await _send_long(query, text)
    return MAIN_MENU


# ── Поиск сессии любой группы ─────────────────────────────────────────────────
async def session_choose_faculty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1 — выбор факультета."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 *Расписание сессии — выберите факультет:*",
        parse_mode="Markdown",
        reply_markup=faculty_keyboard(prefix="session_fac_"),
    )
    return MAIN_MENU


async def session_faculty_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2 — выбор формы обучения."""
    query   = update.callback_query
    await query.answer()
    faculty = query.data.replace("session_fac_", "")
    context.user_data["session_faculty"] = faculty
    fac_name = FACULTIES.get(faculty, faculty)
    await query.edit_message_text(
        f"📝 *Сессия — {fac_name}*\nВыберите форму обучения:",
        parse_mode="Markdown",
        reply_markup=form_keyboard(prefix="session_form_", back="back_main"),
    )
    return MAIN_MENU


async def session_form_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 3 — ввод номера группы."""
    query = update.callback_query
    await query.answer()
    form = query.data.replace("session_form_", "")
    context.user_data["session_form"] = form
    faculty  = context.user_data.get("session_faculty", "")
    fac_name = FACULTIES.get(faculty, faculty)
    form_name = STUDY_FORMS.get(form, form)
    await query.edit_message_text(
        f"📝 *Сессия — {fac_name} / {form_name}*\n\nВведите номер группы:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="back_main")
        ]]),
    )
    return MAIN_MENU


async def session_group_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 4 — загрузка и показ сессии."""
    grp     = update.message.text.strip()
    faculty = context.user_data.get("session_faculty", "")
    form    = context.user_data.get("session_form", "")

    if not faculty or not form:
        await update.message.reply_text("⚠️ Начните поиск заново через меню.")
        return MAIN_MENU

    url = f"{BASE_URL}/schedule/{faculty}/{form}/{grp}/session"
    msg = await update.message.reply_text("⏳ Загружаю расписание сессии…")

    html = await fetch_page(url, use_cache=True, ttl=3600)
    if not html:
        await msg.edit_text(
            "❌ Не удалось загрузить данные. Проверьте номер группы.",
            reply_markup=_back_kb(),
        )
        return MAIN_MENU

    fac_name  = FACULTIES.get(faculty, faculty)
    form_name = STUDY_FORMS.get(form, form)
    header    = f"📝 *Сессия — группа {grp}* | {fac_name} / {form_name}\n{DIVIDER}\n"
    text      = header + parse_session_html(html)

    # удаляем «загружаю...» и шлём результат
    try:
        await msg.delete()
    except Exception:
        pass

    parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for part in parts:
        await update.message.reply_text(part, parse_mode="Markdown",
                                        disable_web_page_preview=True)
    return MAIN_MENU


# ── Вспомогательные ──────────────────────────────────────────────────────────
def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")
    ]])


async def _send_long(query, text: str):
    MAX = 4000
    parts = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    for i, part in enumerate(parts):
        if i == 0:
            await query.edit_message_text(
                part, parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=_back_kb(),
            )
        else:
            await query.message.reply_text(
                part, parse_mode="Markdown",
                disable_web_page_preview=True,
            )
