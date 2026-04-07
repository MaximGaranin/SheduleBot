import os
from dotenv import load_dotenv

load_dotenv()  # читает .env если есть, иначе берёт из окружения

BOT_TOKEN = os.environ["BOT_TOKEN"]
BASE_URL  = os.getenv("BASE_URL", "https://www.sgu.ru")
TIMEZONE  = os.getenv("TIMEZONE", "Europe/Saratov")
PROXY     = os.getenv("PROXY") or None   # None если пустая строка

FACULTIES = {
    "knt":   "КНиИТ",
    "mmf":   "Механико-математический",
    "ff":    "Физический",
    "hf":    "Химический",
    "bf":    "Биологический",
    "gf":    "Географический",
    "gl":    "Геологический",
    "if":    "Исторический",
    "pif":   "Педагогический институт",
    "piii":  "Факультет искусств (ПИ)",
    "ef":    "Экономический",
    "yuf":   "Юридический",
    "uf":    "Юридический (вечерний)",
    "sf":    "Социологический",
    "fmend": "Физ-мат и ест.-науч.",
    "pf":    "Психологический",
    "mf":    "Философский",
    "fip":   "Иностранных языков",
    "in":    "Институт нанотехнологий",
}

STUDY_FORMS = {
    "do": "Дневная форма",
    "zo": "Заочная форма",
    "ov": "Очно-заочная",
}

DAY_NAMES = {
    "Понедельник": "Пн", "Вторник": "Вт", "Среда": "Ср",
    "Четверг": "Чт", "Пятница": "Пт", "Суббота": "Сб",
    "Пн": "Пн", "Вт": "Вт", "Ср": "Ср",
    "Чт": "Чт", "Пт": "Пт", "Сб": "Сб",
}
DAY_EMOJI   = {"Пн": "1️⃣", "Вт": "2️⃣", "Ср": "3️⃣", "Чт": "4️⃣", "Пт": "5️⃣", "Сб": "6️⃣"}
DAYS_ORDER  = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
WEEKDAY_TO_DAY = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: None}

(
    MAIN_MENU,
    CHOOSE_FACULTY,
    CHOOSE_FORM,
    ENTER_GROUP,
    ENTER_TEACHER,
    SETUP_FACULTY,
    SETUP_FORM,
    SETUP_GROUP,
    TEACHER_SELECT_NUMBER,
    ENTER_SESSION_GROUP,
) = range(10)
