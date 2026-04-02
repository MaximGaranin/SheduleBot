from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import FACULTIES, STUDY_FORMS
from database import get_profile


def main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    profile = get_profile(user_id)
    rows = []
    if profile:
        rows.append([
            InlineKeyboardButton("📅 Моё расписание", callback_data="my_schedule"),
            InlineKeyboardButton("🔆 На сегодня",     callback_data="today_schedule"),
        ])
    rows.append([InlineKeyboardButton("📚 Расписание группы",        callback_data="group_schedule")])
    rows.append([InlineKeyboardButton("👨‍🏫 Расписание преподавателя",  callback_data="teacher_schedule")])
    rows.append([InlineKeyboardButton("📋 История поиска",           callback_data="history")])
    rows.append([InlineKeyboardButton("👤 Настроить профиль",        callback_data="setup_profile")])
    rows.append([InlineKeyboardButton("ℹ️ Помощь",                   callback_data="help")])
    return InlineKeyboardMarkup(rows)


def faculty_keyboard(prefix: str = "fac_") -> InlineKeyboardMarkup:
    items = list(FACULTIES.items())
    rows = []
    for i in range(0, len(items), 2):
        row = []
        for code, name in items[i:i+2]:
            short = name[:22] + "…" if len(name) > 22 else name
            row.append(InlineKeyboardButton(short, callback_data=f"{prefix}{code}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def form_keyboard(prefix: str = "form_", back: str = "back_main") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(name, callback_data=f"{prefix}{code}")]
            for code, name in STUDY_FORMS.items()]
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data=back)])
    return InlineKeyboardMarkup(rows)


def my_schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Полное расписание", callback_data="my_schedule"),
         InlineKeyboardButton("🔆 На сегодня",        callback_data="today_schedule")],
        [InlineKeyboardButton("🏠 Главное меню",      callback_data="back_main")],
    ])


def after_teacher_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Другой преподаватель", callback_data="teacher_schedule"),
        InlineKeyboardButton("🏠 Меню",                 callback_data="back_main"),
    ]])
