import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from telegram.request import HTTPXRequest
from config import (
    BOT_TOKEN, PROXY,
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
from handlers.favorites import (
    show_favorites, open_favorite, delete_favorite_handler,
    add_group_to_fav_handler, add_teacher_to_fav_handler,
)

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Фильтр: текст содержит хотя бы 2 русских буквы подряд (ФИО)
FIO_FILTER    = filters.TEXT & ~filters.COMMAND & filters.Regex(r'[А-яЁё]{2,}')
# Фильтр: только цифры (номер группы)
DIGITS_FILTER = filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d{2,4}$')


def make_request(read_timeout: float = 30.0) -> HTTPXRequest:
    kwargs = dict(
        connect_timeout=20.0,
        read_timeout=read_timeout,
        write_timeout=30.0,
        pool_timeout=10.0,
    )
    if PROXY:
        kwargs["proxy"] = PROXY
        logger.info(f"Using proxy: {PROXY}")
    return HTTPXRequest(**kwargs)


async def main_menu_router(update: Update, context):
    query = update.callback_query
    await query.answer()
    d = query.data

    if d == "group_schedule":     return await show_faculties(update, context)
    if d == "teacher_schedule":   return await ask_teacher_name(update, context)
    if d == "setup_profile":      return await setup_profile_start(update, context)
    if d == "my_schedule":        return await show_my_schedule(update, context)
    if d == "today_schedule":     return await show_my_schedule(update, context, only_day="today")
    if d == "back_main":          return await start(update, context)
    if d == "help":               return await help_handler(update, context)
    if d == "history":            return await history_handler(update, context)
    if d == "favorites":          return await show_favorites(update, context)
    if d.startswith("fav_open_"): return await open_favorite(update, context)
    if d.startswith("fav_del_"):  return await delete_favorite_handler(update, context)
    if d.startswith("fav_add_group"):   return await add_group_to_fav_handler(update, context)
    if d.startswith("fav_add_teacher"): return await add_teacher_to_fav_handler(update, context)
    return MAIN_MENU


def build_conv() -> ConversationHandler:
    fav_cb = CallbackQueryHandler(
        main_menu_router,
        pattern=r"^(favorites|fav_open_|fav_del_|fav_add_group|fav_add_teacher)"
    )
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(DIGITS_FILTER, quick_group_input),
            MessageHandler(FIO_FILTER, teacher_query_entered),
        ],
        states={
            MAIN_MENU: [
                fav_cb,
                CallbackQueryHandler(main_menu_router),
                MessageHandler(DIGITS_FILTER, quick_group_input),
                MessageHandler(FIO_FILTER, teacher_query_entered),
            ],
            CHOOSE_FACULTY: [
                CallbackQueryHandler(faculty_chosen, pattern=r"^fac_"),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
                MessageHandler(DIGITS_FILTER, quick_group_input),
            ],
            CHOOSE_FORM: [
                CallbackQueryHandler(form_chosen, pattern=r"^form_"),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
                MessageHandler(DIGITS_FILTER, quick_group_input),
            ],
            ENTER_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, group_entered),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
            ENTER_TEACHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_query_entered),
                CallbackQueryHandler(start, pattern=r"^back_main$"),
            ],
            # В этом состоянии DIGITS_FILTER должен обрабатываться первым,
            # чтобы цифра не уходила в quick_group_input
            TEACHER_SELECT_NUMBER: [
                MessageHandler(DIGITS_FILTER, teacher_number_entered),
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
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(make_request(read_timeout=30.0))
        .get_updates_request(make_request(read_timeout=40.0))
        .build()
    )
    app.add_handler(build_conv())
    logger.info("SGU Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
