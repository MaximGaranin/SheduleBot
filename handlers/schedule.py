import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import (
    BASE_URL, FACULTIES, STUDY_FORMS,
    MAIN_MENU, CHOOSE_FACULTY, CHOOSE_FORM, ENTER_GROUP, WEEKDAY_TO_DAY,
)
from database import get_profile, add_history
from fetcher import fetch_page
from parser import parse_schedule_html
from keyboards import faculty_keyboard, form_keyboard, my_schedule_keyboard
from utils import send_long


async def show_faculties(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(
        "🏛️ *Выберите факультет:*",
        reply_markup=faculty_keyboard(),
        parse_mode="Markdown"
    )
    return CHOOSE_FACULTY


async def faculty_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    faculty_code = query.data.replace("fac_", "")
    context.user_data["faculty"]      = faculty_code
    context.user_data["faculty_name"] = FACULTIES.get(faculty_code, faculty_code)
    await query.edit_message_text(
        f"🏛️ *{context.user_data['faculty_name']}*\n\n📋 Выберите форму обучения:",
        reply_markup=form_keyboard(),
        parse_mode="Markdown"
    )
    return CHOOSE_FORM


async def form_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    form_code = query.data.replace("form_", "")
    context.user_data["form"]      = form_code
    context.user_data["form_name"] = STUDY_FORMS.get(form_code, form_code)
    await query.edit_message_text(
        f"🏛️ *{context.user_data['faculty_name']}*\n"
        f"📋 *{context.user_data['form_name']}*\n\n"
        "🔢 Введите *номер группы*:",
        parse_mode="Markdown"
    )
    return ENTER_GROUP


async def _fetch_and_send(
    message_obj, user_id: int,
    faculty: str, form: str, group: str,
    faculty_name: str, form_name: str,
    only_day: str = None,
) -> bool:
    url = f"{BASE_URL}/schedule/{faculty}/{form}/{group}"
    msg = await message_obj.reply_text(
        f"⏳ Загружаю расписание группы *{group}*...", parse_mode="Markdown"
    )
    html = await fetch_page(url)
    if not html:
        await msg.edit_text(f"❌ Не удалось загрузить страницу.\n{url}")
        return False

    schedule_text = parse_schedule_html(html, only_day=only_day)
    header = (
        f"📅 *Расписание группы {group}*\n"
        f"🏛️ {faculty_name}\n"
        f"📋 {form_name}\n"
        f"🔗 [Открыть на сайте]({url})\n"
        f"{'─'*28}\n"
    )
    await msg.delete()
    await send_long(message_obj, header + schedule_text)

    if user_id:
        add_history(user_id, "group", f"{faculty}/{form}/{group}")
    return True


async def group_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group = update.message.text.strip()
    if not re.match(r'^\d{2,4}[а-яА-Яa-zA-Z]?$', group):
        await update.message.reply_text("❌ Неверный формат группы.")
        return ENTER_GROUP

    ok = await _fetch_and_send(
        update.message, update.effective_user.id,
        context.user_data["faculty"], context.user_data["form"], group,
        context.user_data["faculty_name"], context.user_data["form_name"],
    )
    if ok:
        await update.message.reply_text("Что дальше?", reply_markup=my_schedule_keyboard())
    return MAIN_MENU


async def quick_group_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered when user types only digits — searches in profile faculty."""
    text = update.message.text.strip()
    if not re.match(r'^\d{2,4}$', text):
        return MAIN_MENU

    user_id = update.effective_user.id
    profile = get_profile(user_id)
    if not profile:
        from keyboards import main_keyboard
        await update.message.reply_text(
            "❓ Профиль не настроен. Выберите факультет через меню.",
            reply_markup=main_keyboard(user_id)
        )
        return MAIN_MENU

    fac_name  = FACULTIES.get(profile["faculty"], profile["faculty"])
    form_name = STUDY_FORMS.get(profile["form"],   profile["form"])
    ok = await _fetch_and_send(
        update.message, user_id,
        profile["faculty"], profile["form"], text,
        fac_name, form_name,
    )
    if ok:
        await update.message.reply_text("Что дальше?", reply_markup=my_schedule_keyboard())
    return MAIN_MENU


async def show_my_schedule(
    update: Update, context: ContextTypes.DEFAULT_TYPE, only_day: str = None
) -> int:
    query = update.callback_query
    user_id = update.effective_user.id
    profile = get_profile(user_id)

    if not profile:
        await query.edit_message_text(
            "❌ Профиль не настроен.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👤 Настроить профиль", callback_data="setup_profile"),
                InlineKeyboardButton("◀️ Назад",             callback_data="back_main"),
            ]])
        )
        return MAIN_MENU

    day_filter = None
    if only_day == "today":
        day_filter = WEEKDAY_TO_DAY.get(datetime.now().weekday())
        if day_filter is None:
            await query.edit_message_text(
                "😴 Сегодня воскресенье — занятий нет.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="back_main")
                ]])
            )
            return MAIN_MENU

    await query.delete_message()
    fac_name  = FACULTIES.get(profile["faculty"], profile["faculty"])
    form_name = STUDY_FORMS.get(profile["form"],   profile["form"])
    ok = await _fetch_and_send(
        update.effective_message, user_id,
        profile["faculty"], profile["form"], profile["grp"],
        fac_name, form_name,
        only_day=day_filter,
    )
    if ok:
        await update.effective_message.reply_text(
            "Что дальше?", reply_markup=my_schedule_keyboard()
        )
    return MAIN_MENU
