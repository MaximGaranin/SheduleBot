import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import MAIN_MENU, FACULTIES, STUDY_FORMS, BASE_URL
from database import (
    get_favorites, add_favorite_group, add_favorite_teacher,
    delete_favorite, get_favorite_by_id, MAX_FAVORITES,
)
from fetcher import fetch_page
from parser import parse_schedule_html
from utils import send_long
from keyboards import my_schedule_keyboard

# ———————————————————————————————————————————
#  Список избранного
# ———————————————————————————————————————————

def favorites_keyboard(favs: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard with one fav per row + delete button."""
    rows = []
    for f in favs:
        icon = "📚" if f["fav_type"] == "group" else "👨‍🏫"
        rows.append([
            InlineKeyboardButton(
                f"{icon} {f['label']}",
                callback_data=f"fav_open_{f['id']}"
            ),
            InlineKeyboardButton(
                "🗑️",
                callback_data=f"fav_del_{f['id']}"
            ),
        ])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


async def show_favorites(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    favs = get_favorites(user_id)

    if not favs:
        text = (
            "⭐ *Избранное пусто.*\n\n"
            "Добавляйте группы и преподавателей через кнопку "
            "\u2b50 после получения расписания."
        )
    else:
        count = len(favs)
        text = (
            f"⭐ *Избранное* ({count}/{MAX_FAVORITES})\n\n"
            "Нажмите на запись — получите расписание.\n"
            "🗑️ — удалить запись."
        )

    kb = favorites_keyboard(favs) if favs else InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Назад", callback_data="back_main")
    ]])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    return MAIN_MENU


# ———————————————————————————————————————————
#  Открыть / удалить
# ———————————————————————————————————————————

async def open_favorite(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    fav_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id
    fav = get_favorite_by_id(fav_id, user_id)

    if not fav:
        await query.edit_message_text("❌ Запись не найдена.")
        return MAIN_MENU

    if fav["fav_type"] == "group":
        return await _open_group_fav(update, fav)
    else:
        return await _open_teacher_fav(update, fav)


async def _open_group_fav(update: Update, fav: dict) -> int:
    query = update.callback_query
    faculty  = fav["faculty"]
    form     = fav["form"]
    grp      = fav["grp"]
    url      = f"{BASE_URL}/schedule/{faculty}/{form}/{grp}"
    fac_name = FACULTIES.get(faculty, faculty)
    frm_name = STUDY_FORMS.get(form, form)

    await query.edit_message_text(
        f"⏳ Загружаю расписание группы *{grp}*...",
        parse_mode="Markdown"
    )
    html = await fetch_page(url)
    if not html:
        await query.edit_message_text(f"❌ Не удалось загрузить.\n{url}")
        return MAIN_MENU

    text = (
        f"📅 *Расписание группы {grp}*\n"
        f"🏛️ {fac_name}\n📋 {frm_name}\n"
        f"🔗 [{url}]({url})\n"
        f"{─*28}\n"
        + parse_schedule_html(html)
    )
    await query.delete_message()
    await send_long(update.effective_message, text)
    await update.effective_message.reply_text(
        "Что дальше?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Избранное", callback_data="favorites"),
            InlineKeyboardButton("🏠 Меню",        callback_data="back_main"),
        ]])
    )
    return MAIN_MENU


async def _open_teacher_fav(update: Update, fav: dict) -> int:
    query = update.callback_query
    await query.edit_message_text(
        f"⏳ Загружаю расписание *{fav['teacher_name']}*...",
        parse_mode="Markdown"
    )
    html = await fetch_page(fav["teacher_url"])
    if not html:
        await query.edit_message_text("❌ Не удалось загрузить расписание.")
        return MAIN_MENU

    text = (
        f"👨‍🏫 *{fav['teacher_name']}*\n"
        f"🔗 [На сайте]({fav['teacher_url']})\n"
        f"{─*28}\n"
        + parse_schedule_html(html)
    )
    await query.delete_message()
    await send_long(update.effective_message, text)
    await update.effective_message.reply_text(
        "Что дальше?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Избранное", callback_data="favorites"),
            InlineKeyboardButton("🏠 Меню",        callback_data="back_main"),
        ]])
    )
    return MAIN_MENU


async def delete_favorite_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    fav_id  = int(query.data.split("_")[-1])
    user_id = update.effective_user.id
    fav     = get_favorite_by_id(fav_id, user_id)
    label   = fav["label"] if fav else "?"
    delete_favorite(user_id, fav_id)
    await query.answer(f"✅ \u00ab{label}\u00bb удалено из избранного.", show_alert=False)
    # Reload list
    favs = get_favorites(user_id)
    if not favs:
        await query.edit_message_text(
            "⭐ *Избранное пусто.*",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_main")
            ]]),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"⭐ *Избранное* ({len(favs)}/{MAX_FAVORITES})",
            reply_markup=favorites_keyboard(favs),
            parse_mode="Markdown"
        )
    return MAIN_MENU


# ———————————————————————————————————————————
#  Добавление в избранное  (callback из schedule.py / teacher.py)
# ———————————————————————————————————————————

async def add_group_to_fav_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Callback data: fav_add_group|faculty|form|grp
    """
    query = update.callback_query
    await query.answer()
    _, _, _, faculty, form, grp = query.data.split("|")
    user_id  = update.effective_user.id
    fac_name = FACULTIES.get(faculty, faculty)
    label    = f"Гр. {grp} ({fac_name[:12]})"
    ok = add_favorite_group(user_id, label, faculty, form, grp)
    if ok:
        await query.answer(f"⭐ \u00ab{label}\u00bb добавлено!", show_alert=True)
    else:
        await query.answer(
            f"⚠️ Уже есть или достигнут лимит {MAX_FAVORITES}.",
            show_alert=True
        )
    return MAIN_MENU


async def add_teacher_to_fav_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Callback data: fav_add_teacher|teacher_name|teacher_url
    """
    query = update.callback_query
    await query.answer()
    parts        = query.data.split("|", 3)
    teacher_name = parts[2]
    teacher_url  = parts[3]
    user_id      = update.effective_user.id
    label        = teacher_name[:40]
    ok = add_favorite_teacher(user_id, label, teacher_name, teacher_url)
    if ok:
        await query.answer(f"⭐ \u00ab{label}\u00bb добавлено!", show_alert=True)
    else:
        await query.answer(
            f"⚠️ Уже есть или достигнут лимит {MAX_FAVORITES}.",
            show_alert=True
        )
    return MAIN_MENU
