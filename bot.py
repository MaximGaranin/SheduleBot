import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from config import (
    BOT_TOKEN,
    MAIN_MENU, CHOOSE_FACULTY, CHOOSE_FORM, ENTER_GROUP,
    ENTER_TEACHER, SETUP_FACULTY, SETUP_FORM, SETUP_GROUP,
    TEACHER_SELECT_NUMBER,
)
from database import init_db
from handlers.menu import start, help_handler, history_handler
from handlers.profile import (
    setup_profile_start, setup_faculty_chosen,
    setup_form_chosen, setup_group_entered,
)
from handlers.schedule import (
    show_faculties, faculty_chosen, form_chosen,
    group_entered, quick_group_input, show_my_schedule,
)
from handlers.teacher import (
    ask_teacher_name, teacher_query_entered, teacher_number_entered,
)

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main_menu_router(update, context):
    query = update.callback_query
    await query.answer()
    d = query.data

    if d == "group_schedule":   return await show_faculties(update, context)
    if d == "teacher_schedule": return await ask_teacher_name(update, context)
    if d == "setup_profile":    return await setup_profile_start(update, context)
    if d == "my_schedule":      return await show_my_schedule(update, context)
    if d == "today_schedule":   return await show_my_schedule(update, context, only_day="today")
    if d == "back_main":        return await start(update, context)
    if d == "help":             return await help_handler(update, context)
    if d == "history":          return await history_handler(update, context)
    return MAIN_MENU


def build_conv() -> ConversationHandler:
    digits = filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d{2,4}$')
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(digits, quick_group_input),
        ],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_router),
                MessageHandler(digits, quick_group_input),
            ],
            CHOOSE_FACULTY: [
                CallbackQueryHandler(faculty_chosen, pattern=r"^fac_"),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
                MessageHandler(digits, quick_group_input),
            ],
            CHOOSE_FORM: [
                CallbackQueryHandler(form_chosen, pattern=r"^form_"),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
                MessageHandler(digits, quick_group_input),
            ],
            ENTER_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, group_entered),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
            ENTER_TEACHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_query_entered),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
            TEACHER_SELECT_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_number_entered),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
            SETUP_FACULTY: [
                CallbackQueryHandler(setup_faculty_chosen, pattern=r"^sp_fac_"),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
            SETUP_FORM: [
                CallbackQueryHandler(setup_form_chosen, pattern=r"^sp_form_"),
                CallbackQueryHandler(setup_profile_start, pattern=r"^setup_profile$"),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
            SETUP_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_group_entered),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(build_conv())
    logger.info("SGU Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
