import re
from telegram import Update
from telegram.ext import ContextTypes
from config import FACULTIES, STUDY_FORMS, MAIN_MENU, SETUP_FACULTY, SETUP_FORM, SETUP_GROUP
from keyboards import faculty_keyboard, form_keyboard, my_schedule_keyboard
from database import save_profile, delete_profile


async def setup_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(
        "👤 *Настройка профиля*\n\nШаг 1/3: Выберите ваш факультет:",
        reply_markup=faculty_keyboard(prefix="sp_fac_"),
        parse_mode="Markdown"
    )
    return SETUP_FACULTY


async def setup_faculty_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    faculty_code = query.data.replace("sp_fac_", "")
    context.user_data["sp_faculty"]      = faculty_code
    context.user_data["sp_faculty_name"] = FACULTIES.get(faculty_code, faculty_code)
    await query.edit_message_text(
        f"👤 *Настройка профиля*\n"
        f"🏛️ {context.user_data['sp_faculty_name']}\n\n"
        "Шаг 2/3: Выберите форму обучения:",
        reply_markup=form_keyboard(prefix="sp_form_", back="setup_profile"),
        parse_mode="Markdown"
    )
    return SETUP_FORM


async def setup_form_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "setup_profile":
        return await setup_profile_start(update, context)
    form_code = query.data.replace("sp_form_", "")
    context.user_data["sp_form"]      = form_code
    context.user_data["sp_form_name"] = STUDY_FORMS.get(form_code, form_code)
    await query.edit_message_text(
        f"👤 *Настройка профиля*\n"
        f"🏛️ {context.user_data['sp_faculty_name']}\n"
        f"📋 {context.user_data['sp_form_name']}\n\n"
        "Шаг 3/3: Введите *номер вашей группы* (например: 221):",
        parse_mode="Markdown"
    )
    return SETUP_GROUP


async def setup_group_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group = update.message.text.strip()
    if not re.match(r'^\d{2,4}[а-яА-Яa-zA-Z]?$', group):
        await update.message.reply_text("❌ Неверный формат. Введите номер группы:")
        return SETUP_GROUP

    user_id = update.effective_user.id
    save_profile(
        user_id,
        context.user_data["sp_faculty"],
        context.user_data["sp_form"],
        group,
    )

    fac_name  = FACULTIES.get(context.user_data["sp_faculty"], "")
    form_name = STUDY_FORMS.get(context.user_data["sp_form"], "")
    await update.message.reply_text(
        f"✅ *Профиль сохранён!*\n\n"
        f"🏛️ {fac_name}\n"
        f"📋 {form_name}\n"
        f"👥 Группа: *{group}*\n\n"
        "Данные сохранены в SQLite и не пропадут при перезапуске.",
        reply_markup=my_schedule_keyboard(),
        parse_mode="Markdown"
    )
    return MAIN_MENU
