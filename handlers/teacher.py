import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import BASE_URL, MAIN_MENU, ENTER_TEACHER, TEACHER_SELECT_NUMBER
from database import get_cached_teachers, save_cached_teachers, add_history
from fetcher import fetch_page
from parser import parse_schedule_html, search_teachers, _score_teacher
from utils import send_long

DIVIDER = "─" * 28


def _after_teacher_keyboard(teacher_name: str, teacher_url: str) -> InlineKeyboardMarkup:
    fav_data = f"fav_add_teacher|fav|add|{teacher_name}|{teacher_url}"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐ В избранное",           callback_data=fav_data),
        InlineKeyboardButton("🔄 Другой преподаватель",  callback_data="teacher_schedule"),
    ], [
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_main"),
    ]])


async def ask_teacher_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Called from button — show hint and wait for input."""
    query = update.callback_query
    await query.edit_message_text(
        "👨‍🏫 *Поиск преподавателя*\n\n"
        "Введите ФИО или часть фамилии. Примеры:\n"
        "`Иванов`\n"
        "`Иванов Иван`\n"
        "`Иванов Иван Иванович`\n"
        "`Иванов И.И.`",
        parse_mode="Markdown"
    )
    return ENTER_TEACHER


async def teacher_query_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка текстового ввода ФИО.
    Вызывается как из MAIN_MENU (прямой ввод), так и из ENTER_TEACHER (после кнопки).
    """
    text = update.message.text.strip()

    # Если ввели только цифру — выбор из списка
    if re.match(r'^\d+$', text):
        return await teacher_number_entered(update, context)

    if len(text) < 2:
        await update.message.reply_text("❌ Слишком коротко. Введите фамилию.")
        return ENTER_TEACHER

    # Валидация: есть ли русские буквы
    if not re.search(r'[А-яЁё]', text):
        await update.message.reply_text(
            "❌ Введите фамилию на русском языке.\n"
            "Пример: `Иванов` или `Иванов Иван Иванович`",
            parse_mode="Markdown"
        )
        return ENTER_TEACHER

    msg = await update.message.reply_text(
        f"🔍 Ищу преподавателя: *{text}*...",
        parse_mode="Markdown"
    )

    # Кэш по первому слову
    first_word = text.split()[0]
    results    = get_cached_teachers(first_word)
    source     = "кэш"

    if results is None:
        html = await fetch_page(f"{BASE_URL}/schedule", use_cache=False)
        if not html:
            await msg.edit_text("❌ Не удалось подключиться к сайту СГУ.")
            return MAIN_MENU
        results = search_teachers(html, text)
        if results:
            save_cached_teachers(first_word, results)
        source = "сайт"
    elif len(text.split()) > 1:
        # Дофильтрация кэша по остальным словам
        words   = [w for w in re.split(r'[\s,.]+', text.lower()) if len(w) >= 2]
        results = [r for r in results if _score_teacher(r["name"].lower(), words) > 0]

    if not results:
        await msg.edit_text(
            f"❌ По запросу *{text}* никого не найдено.\n"
            "Попробуйте ввести только фамилию.",
            parse_mode="Markdown"
        )
        return ENTER_TEACHER

    add_history(update.effective_user.id, "teacher", text)

    if len(results) == 1:
        await msg.edit_text(
            f"✅ Найден: *{results[0]['name']}* ({source})",
            parse_mode="Markdown"
        )
        return await _load_teacher_schedule(update, results[0])

    # Показываем ВСЕХ найденных без ограничений
    context.user_data["teacher_results"] = results
    lines = [f"🔍 *Найдено {len(results)} преподавателя* ({source}):\n"]
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
        await update.message.reply_text("❓ Список устарел. Введите ФИО заново.")
        return ENTER_TEACHER
    num = int(text)
    if num < 1 or num > len(results):
        await update.message.reply_text(f"❌ Введите число от 1 до {len(results)}.")
        return TEACHER_SELECT_NUMBER
    return await _load_teacher_schedule(update, results[num - 1])


async def _load_teacher_schedule(update: Update, teacher: dict) -> int:
    msg = await update.message.reply_text(
        f"⏳ Загружаю расписание *{teacher['name']}*...",
        parse_mode="Markdown"
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
