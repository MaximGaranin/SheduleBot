import re
from bs4 import BeautifulSoup
from config import DAY_NAMES, DAY_EMOJI, DAYS_ORDER, BASE_URL


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _parse_horizontal(rows, header_row_idx) -> dict:
    day_col = {}
    for row in rows[:header_row_idx + 1]:
        cells = row.find_all(["td", "th"])
        for c_idx, cell in enumerate(cells):
            txt = clean(cell.get_text())
            short = DAY_NAMES.get(txt)
            if short:
                day_col[c_idx] = short

    if not day_col:
        return {day: [] for day in DAYS_ORDER}

    min_day_col = min(day_col.keys())
    if min_day_col == 0:
        day_col = {k + 1: v for k, v in day_col.items()}

    schedule = {day: [] for day in DAYS_ORDER}
    data_start = header_row_idx + 1

    while data_start < len(rows):
        cells = rows[data_start].find_all(["td", "th"])
        texts = [clean(c.get_text()) for c in cells]
        if any(DAY_NAMES.get(t) for t in texts):
            data_start += 1
        else:
            break

    for row in rows[data_start:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        time_val = clean(cells[0].get_text())
        if not re.search(r'\d{1,2}:\d{2}', time_val):
            continue
        for c_idx, day in day_col.items():
            if c_idx < len(cells):
                lesson = clean(cells[c_idx].get_text(" "))
                if lesson and lesson not in ["-", "–", "—", ""]:
                    schedule[day].append((time_val, lesson))
    return schedule


def _parse_vertical(rows) -> dict:
    schedule = {day: [] for day in DAYS_ORDER}
    current_day = None

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [clean(c.get_text(" ")) for c in cells]

        if len(texts) == 1:
            short = DAY_NAMES.get(texts[0])
            if short:
                current_day = short
            continue

        first_short = DAY_NAMES.get(texts[0])
        if first_short:
            current_day = first_short
            texts = texts[1:]

        if current_day is None:
            continue

        time_val = None
        lesson_parts = []
        for t in texts:
            if re.search(r'\d{1,2}:\d{2}', t) and time_val is None:
                time_val = t
            elif t and t not in ["-", "–", "—"]:
                lesson_parts.append(t)

        if time_val and lesson_parts:
            schedule[current_day].append((time_val, " ".join(lesson_parts)))

    return schedule


def _format_schedule(schedule: dict, only_day: str = None) -> str:
    days_to_show = [only_day] if only_day else DAYS_ORDER
    lines = []
    for day in days_to_show:
        entries = schedule.get(day, [])
        if not entries:
            if only_day:
                return f"💭 В *{day}* занятий нет."
            continue
        lines.append(f"\n{DAY_EMOJI.get(day, '📅')} *{day}*")
        for time_val, lesson in entries:
            time_fmt = re.sub(r'(\d{2}:\d{2})\s+(\d{2}:\d{2})', r'\1–\2', time_val)
            lines.append(f"  ⏰ `{time_fmt}`")
            parts = re.split(r'(?=ЛЕКЦИЯ|ПРАКТИКА|СЕМИНАР|ЛАБОРАТОРНАЯ)', lesson)
            for part in parts:
                part = part.strip()
                if part:
                    lines.append(f"     {part}")
    return "\n".join(lines) if lines else "⚠️ Занятий не найдено."


def parse_schedule_html(html: str, only_day: str = None) -> str:
    soup = BeautifulSoup(html, "html.parser")

    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text()
        if "Понедельник" in text or ("Пн" in text and "Вт" in text and "Ср" in text):
            target_table = table
            break

    if not target_table:
        body = soup.find("div", class_=re.compile(r"schedule|content-inner|field-items", re.I))
        return body.get_text("\n", strip=True)[:3000] if body else "⚠️ Расписание не найдено."

    rows = target_table.find_all("tr")
    if len(rows) < 2:
        return "⚠️ Таблица пустая."

    header_row_idx = None
    day_col = {}
    for r_idx, row in enumerate(rows[:3]):
        cells = row.find_all(["td", "th"])
        for c_idx, cell in enumerate(cells):
            txt = clean(cell.get_text())
            short = DAY_NAMES.get(txt)
            if short:
                day_col[c_idx] = short
        if day_col:
            header_row_idx = r_idx
            break

    if day_col:
        schedule = _parse_horizontal(rows, header_row_idx)
    else:
        schedule = _parse_vertical(rows)

    return _format_schedule(schedule, only_day)


# ─── Парсинг расписания сессии ───────────────────────────────────────────────

# Русские названия месяцев для формата «13 апреля 2026 г. 10:00»
_RU_MONTHS = {
    "января": "01", "февраля": "02", "марта": "03",
    "апреля": "04", "мая": "05",     "июня": "06",
    "июля": "07",  "августа": "08", "сентября": "09",
    "октября": "10", "ноября": "11",  "декабря": "12",
}

# Типы событий сессии
_SESSION_TYPES = [
    ("экзамен",                   "📝"),
    ("дифференцированный зачет",  "📊"),
    ("диф. зачет",              "📊"),
    ("консультация",            "💬"),
    ("курсовая",               "📐"),
    ("зачет",                  "✅"),
    ("зачёт",                  "✅"),
    ("лабораторная",           "🔬"),
    ("практика",               "📝"),
    ("лекция",                "📖"),
]


def _event_emoji(kind: str, subject: str = "") -> str:
    text = (kind + " " + subject).lower()
    for key, emoji in _SESSION_TYPES:
        if key in text:
            return emoji
    return "📌"


def _parse_ru_date(raw: str):
    """Парсит дату и время в любом из форматов:
      - '13 апреля 2026 г. 10:00'
      - '2026-04-13 10:00:00'
      - '13.04.2026 10:00'
    Возвращает (date_str, time_str)
    """
    raw = raw.strip()

    # ISO: 2026-04-13 10:00:00
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}:\d{2}))?', raw)
    if m:
        date_str = f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
        time_str = m.group(4) or ""
        return date_str, time_str

    # Русский: 13 апреля 2026 г. 10:00
    m = re.match(
        r'(\d{1,2})\s+([\u0430-я]+)\s+(\d{4})(?:\s*г\.?)?(?:\s+(\d{1,2}:\d{2}))?',
        raw, re.IGNORECASE
    )
    if m:
        day   = m.group(1).zfill(2)
        month = _RU_MONTHS.get(m.group(2).lower(), "??")
        year  = m.group(3)
        time_str = m.group(4) or ""
        date_str = f"{day}.{month}.{year}"
        return date_str, time_str

    # DD.MM.YYYY HH:MM
    m = re.match(r'(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{1,2}:\d{2}))?', raw)
    if m:
        return m.group(1), m.group(2) or ""

    # Если ничего не подошло — извлечем время
    mt = re.search(r'(\d{1,2}:\d{2})', raw)
    time_str = mt.group(1) if mt else ""
    date_str = raw[:mt.start()].strip() if mt else raw
    return date_str, time_str


# Типы событий в начале строки (заочники)
# Пример: "ЭкзаменСтруктуры данных" → kind="Экзамен", subject="Структуры данных"
_TYPE_PREFIX_RE = re.compile(
    r'^(Экзамен|Дифференцированный\s+зач[её]т|Консультация|Зач[её]т|Курсовая|Лабораторная|Практика|Лекция)',
    re.IGNORECASE,
)

# Тип в конце строки (дневники)
_TYPE_SUFFIX_RE = re.compile(
    r'\s+(Экзамен|Дифференцированный\s+зач[её]т|Консультация|Зач[её]т|Курсовая)$',
    re.IGNORECASE,
)


def _split_subject_kind(raw: str):
    """Разделяет тип события и название дисциплины.

    Поддерживает два формата:
      1. Заочники: тип в НАЧАЛЕ без пробела
         "ЭкзаменСтруктуры данных" → ("Структуры данных", "Экзамен")
      2. Дневники: тип в КОНЦЕ через пробел
         "Микроэкономика Экзамен" → ("Микроэкономика", "Экзамен")
    """
    raw = raw.strip()

    # Сначала пробуем формат заочников: тип в начале без пробела
    m = _TYPE_PREFIX_RE.match(raw)
    if m:
        kind    = m.group(1).strip()
        subject = raw[m.end():].strip()
        return subject, kind

    # Затем формат дневников: тип в конце через пробел
    m = _TYPE_SUFFIX_RE.search(raw)
    if m:
        kind    = m.group(1).strip()
        subject = raw[:m.start()].strip()
        return subject, kind

    return raw, ""


def _is_session_empty(soup: BeautifulSoup) -> bool:
    page_text = soup.get_text(" ", strip=True).lower()
    empty_markers = [
        "расписание не сформировано",
        "расписание отсутствует",
        "нет данных",
        "нет записей",
        "не заполнено",
        "no data",
        "not found",
    ]
    for marker in empty_markers:
        if marker in page_text:
            return True

    # Нет дат — сессия пуста
    has_date = bool(
        re.search(r'\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}', page_text) or
        any(m in page_text for m in _RU_MONTHS)
    )
    if not has_date:
        tables = soup.find_all("table")
        has_data = any(len(t.find_all("tr")) >= 2 for t in tables)
        if not has_data:
            return True

    return False


def parse_session_html(html: str) -> str:
    """Парсит страницу /schedule/{fac}/{form}/{grp}/session.

    Поддерживает два формата:

    Дневники (колонка «Дисциплина», тип в конце):
      2026-01-13 13:50:00 | Микроэкономика Экзамен | Иванов И.И. | 12-518

    Заочники (колонка «Отчётность / Дисциплина», тип в начале):
      13 апреля 2026 г. 10:00 | ЭкзаменСтруктуры данных | Батраева И.А. | 12 корпус, 314 комната
    """
    soup = BeautifulSoup(html, "html.parser")

    if _is_session_empty(soup):
        return "📭 Расписание сессии ещё не заполнено."

    # Ищем таблицу:
    # Дневники: Дисциплина + Преподаватель
    # Заочники: Отчётность / Дисциплина + Преподаватель
    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if ("дисциплин" in text.lower()) and \
           ("преподаватель" in text.lower() or "место" in text.lower()):
            target_table = table
            break

    # Фолбэк: любая таблица с ISO или русской датой
    if not target_table:
        for table in soup.find_all("table"):
            t = table.get_text()
            if re.search(r'\d{4}-\d{2}-\d{2}', t) or \
               any(m in t.lower() for m in _RU_MONTHS):
                target_table = table
                break

    if not target_table:
        return "📭 Расписание сессии ещё не заполнено."

    rows = target_table.find_all("tr")
    if len(rows) < 2:
        return "📭 Расписание сессии ещё не заполнено."

    # Определяем индексы колонок
    header_cells = rows[0].find_all(["td", "th"])
    headers = [clean(c.get_text()).lower() for c in header_cells]

    def _col(*keywords):
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return None

    col_date    = _col("дата", "число") 
    col_subject = _col("дисциплин", "отчётность", "предмет")
    col_teacher = _col("преподаватель", "препод", "фио")
    col_room    = _col("место", "аудитория", "кабинет", "ауд")

    # Фаллбэк по позиции
    if col_date    is None: col_date    = 0
    if col_subject is None: col_subject = 1
    if col_teacher is None: col_teacher = 2
    if col_room    is None: col_room    = 3

    entries = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        texts = [clean(c.get_text(" ")) for c in cells]

        def g(idx):
            if idx < len(texts):
                v = texts[idx]
                return v if v not in ("-", "–", "—", "") else ""
            return ""

        date_raw    = g(col_date)
        subject_raw = g(col_subject)
        teacher     = g(col_teacher)
        room        = g(col_room)

        if not date_raw and not subject_raw:
            continue
        # Пропускаем строку заголовки
        if date_raw.lower() in headers or subject_raw.lower() in headers:
            continue

        date_str, time_str = _parse_ru_date(date_raw)
        subject, kind = _split_subject_kind(subject_raw)
        emoji = _event_emoji(kind, subject)

        line = f"{emoji} *{date_str}*"
        if time_str:
            line += f" `{time_str}`"
        if kind:
            line += f" — _{kind}_"
        line += f"\n    📖 {subject}"
        if teacher:
            line += f"\n    👤 {teacher}"
        if room:
            line += f"\n    🚪 {room}"

        entries.append(line)

    if not entries:
        return "📭 Расписание сессии ещё не заполнено."

    return "📋 *Расписание сессии:*\n\n" + "\n\n".join(entries)


# ─── Поиск преподавателей ────────────────────────────────────────────────────────

def _score_teacher(name_lower: str, words: list[str]) -> int:
    tokens = name_lower.split()
    total = 0
    for word in words:
        if word in tokens:
            total += 3
        elif any(t.startswith(word) for t in tokens):
            total += 2
        elif word in name_lower:
            total += 1
        else:
            return 0
    return total


def search_teachers(html: str, query: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    raw_words = re.split(r'[\s,.]+', query.strip().lower())
    words = [w for w in raw_words if len(w) >= 2]
    if not words:
        return []

    results = []
    seen_urls = set()

    for a in soup.find_all("a"):
        link_text = clean(a.get_text())
        href = a.get("href", "")
        if not ("/schedule/" in href and len(link_text) > 3):
            continue
        score = _score_teacher(link_text.lower(), words)
        if score == 0:
            continue
        full_url = BASE_URL + href if href.startswith("/") else href
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        results.append({"name": link_text, "url": full_url, "score": score})

    results.sort(key=lambda x: (-x["score"], x["name"]))
    return [{"name": r["name"], "url": r["url"]} for r in results]
