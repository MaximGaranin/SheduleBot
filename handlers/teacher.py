import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import BASE_URL, MAIN_MENU, ENTER_TEACHER, TEACHER_SELECT_NUMBER
from database import get_cached_teachers, save_cached_teachers, add_history
from fetcher import fetch_page
from parser import parse_schedule_html, search_teachers
from utils import send_long

DIVIDER = "─" * 28


def _after_teacher_keyboard(teacher_name: str, teacher_url: str) -> InlineKeyboardMarkup:
    fav_data = f"fav_add_teacher|fav|add|{teacher_name}|{teacher_url}"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐ В избранное",      callback_data=fav_data),
        InlineKeyboardButton("🔄 Другой преподаватель", callback_data="teacher_schedule"),
    ], [
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_main"),
    ]])


async def ask_teacher_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(
        "👨‍🏫 *Поиск преподавателя*\n\n"
        "Введите фамилию или ФИО.\n"
        "Если найдено несколько — отправьте *номер* из списка.",
        parse_mode="Markdown"
    )
    return ENTER_TEACHER


async def teacher_query_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if re.match(r'^\d+$', text):
        return await teacher_number_entered(update, context)
    if len(text) < 2:
        await update.message.reply_text("❌ Введите минимум 2 символа.")
        return ENTER_TEACHER

    msg = await update.message.reply_text(f"🔍 Ищу: *{text}*...", parse_mode="Markdown")
    results = get_cached_teachers(text)
    source  = "кэш"

    if results is None:
        html = await fetch_page(f"{BASE_URL}/schedule", use_cache=False)
        if not html:
            await msg.edit_text("❌ Не удалось подключиться к сайту СГУ.")
            return MAIN_MENU
        results = search_teachers(html, text)
        if results:
            save_cached_teachers(text, results)
        source = "сайт"

    if not results:
        await msg.edit_text(
            f"❌ По запросу *{text}* никого не найдено.\n"
            f"Проверьте: {BASE_URL}/schedule",
            parse_mode="Markdown"
        )
        return MAIN_MENU

    add_history(update.effective_user.id, "teacher", text)

    if len(results) == 1:
        await msg.edit_text(f"✅ Найден: *{results[0]['name']}* ({source})", parse_mode="Markdown")
        return await _load_teacher_schedule(update, results[0])

    context.user_data["teacher_results"] = results
    lines = [f"🔍 Найдено *{len(results)}* преподавателей ({source}):\n"]
    for i, t in enumerate(results, 1):
        lines.append(f"*{i}.* {t['name']}")
    lines.append("\n✏️ Введите *номер* преподавателя:")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")
    return TEACHER_SELECT_NUMBER


async def teacher_number_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not re.match(r'^\d+$', text):
        await update.message.reply_text("❌ Введите число из списка.")
        return TEACHER_SELECT_NUMBER
    results = context.user_data.get("teacher_results", [])
    if not results:
        await update.message.reply_text("❓ Список устарел. Введите фамилию заново.")
        return ENTER_TEACHER
    num = int(text)
    if num < 1 or num > len(results):
        await update.message.reply_text(f"❌ Введите число от 1 до {len(results)}.")
        return TEACHER_SELECT_NUMBER
    return await _load_teacher_schedule(update, results[num - 1])


async def _load_teacher_schedule(update: Update, teacher: dict) -> int:
    msg = await update.message.reply_text(
        f"⏳ Загружаю расписание *{teacher['name']}*...", parse_mode="Markdown"
    )
    html = await fetch_page(teacher["url"], use_cache=True)
    if not html:
        await msg.edit_text("❌ Не удалось загрузить расписание.")
        return MAIN_MENU
    schedule_text = parse_schedule_html(html)
    full_text = (
        f"👨‍🏫 *{teacher['name']}*\n"
        f"🔗 [На сайте]({teacher['url']})\n"
        f"{DIVIDER}\n"
        + schedule_text
    )
    await msg.delete()
    await send_long(update.message, full_text)
    await update.message.reply_text(
        "Что дальше?",
        reply_markup=_after_teacher_keyboard(teacher["name"], teacher["url"])
    )
    return MAIN_MENU
