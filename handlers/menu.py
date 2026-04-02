from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import MAIN_MENU
from keyboards import main_keyboard
from utils import profile_info
from database import get_profile, get_history


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    text = "🎓 *Расписание СГУ*\n\n" + profile_info(user_id) + "\n\nВыберите действие:"
    markup = main_keyboard(user_id)
    if update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    return MAIN_MENU


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    profile = get_profile(update.effective_user.id)
    hint = (
        "\n\n💡 *Быстрый ввод:* напишите номер группы — "
        "бот найдёт её на вашем факультете."
        if profile else ""
    )
    await query.edit_message_text(
        "ℹ️ *Помощь*\n\n"
        "*📅 Моё расписание* — полное расписание вашей группы\n"
        "*🔆 На сегодня* — только сегодняшние пары\n"
        "*📚 Расписание группы* — найти любую группу\n"
        "*👨‍🏫 Преподаватель* — поиск по фамилии / ФИО\n"
        "*📋 История поиска* — последние 10 запросов\n"
        "*👤 Настроить профиль* — сохранить факультет и группу"
        + hint,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="back_main")
        ]]),
        parse_mode="Markdown"
    )
    return MAIN_MENU


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    history = get_history(user_id, limit=10)

    if not history:
        text = "📋 *История поиска пуста.*"
    else:
        icons = {"group": "📚", "teacher": "👨‍🏫"}
        lines = ["📋 *Последние поиски:*\n"]
        for h in history:
            icon = icons.get(h["search_type"], "🔍")
            dt = h["searched_at"][:16].replace("T", " ")
            lines.append(f"{icon} `{h['query']}` — _{dt}_")
        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="back_main")
        ]]),
        parse_mode="Markdown"
    )
    return MAIN_MENU
