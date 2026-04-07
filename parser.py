import re
from bs4 import BeautifulSoup
from config import DAY_NAMES, DAY_EMOJI, DAYS_ORDER, BASE_URL


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _parse_horizontal(rows, header_row_idx) -> dict:
    """Горизонтальная таблица: дни = столбцы."""
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
    """Вертикальная таблица: дни = строки."""
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

# Типы событий сессии — указаны в поле "Дисциплина" прямо в конце строки
# Например: "Микроэкономика Экзамен"
_SESSION_TYPES = [
    ("экзамен",                   "📝"),
    ("дифференцированный зачет",  "📊"),
    ("диф. зачет",              "📊"),
    ("консультация",            "💬"),
    ("курсовая",               "📐"),
    ("зачет",                  "✅"),
    ("зачёт",                  "✅"),
]

# Регексп для извлечения типа события из конца строки дисциплины
# "Микроэкономика Экзамен" → subject="Микроэкономика", kind="Экзамен"
_TYPE_RE = re.compile(
    r'\s+((Экзамен|Дифференцированный\s+зач[её]т|Консультация|Зач[её]т|Курсовая))$',
    re.IGNORECASE,
)


def _split_subject_kind(raw: str):
    """"Микроэкономика Экзамен" → ("Микроэкономика", "Экзамен")"""
    m = _TYPE_RE.search(raw)
    if m:
        kind = m.group(1).strip()
        subject = raw[:m.start()].strip()
        return subject, kind
    return raw.strip(), ""


def _event_emoji(kind: str, subject: str = "") -> str:
    text = (kind + " " + subject).lower()
    for key, emoji in _SESSION_TYPES:
        if key in text:
            return emoji
    return "📌"


def parse_session_html(html: str) -> str:
    """Парсит страницу /schedule/{fac}/{form}/{grp}/session СГУ.

    Реальный формат таблицы:
      Дата               | Дисциплина                       | Преподаватель | Место
      2026-01-13 13:50:00 | Микроэкономика Экзамен | Иванов И.И. | 12-518
    """
    soup = BeautifulSoup(html, "html.parser")

    # Ищем таблицу с нужными столбцами (Дисциплина + Преподаватель)
    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if "Дисциплина" in text and "Преподаватель" in text:
            target_table = table
            break

    # Фолбэк: любая таблица с ISO-датами
    if not target_table:
        for table in soup.find_all("table"):
            if re.search(r'\d{4}-\d{2}-\d{2}', table.get_text()):
                target_table = table
                break

    if not target_table:
        body = soup.find("div", class_=re.compile(
            r"schedule|content-inner|field-items|view-content", re.I))
        raw = body.get_text("\n", strip=True) if body else ""
        if raw and len(raw) > 20:
            return "📋 *Расписание сессии:*\n\n" + raw[:3000]
        return "📭 Расписание сессии пока не опубликовано."

    rows = target_table.find_all("tr")
    if len(rows) < 2:
        return "📭 Расписание сессии пока не опубликовано."

    # Определяем индексы колонок по заголовке
    header_cells = rows[0].find_all(["td", "th"])
    headers = [clean(c.get_text()).lower() for c in header_cells]

    def _col(*keywords):
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return None

    col_date    = _col("дата", "число")
    col_subject = _col("дисциплин", "предмет")
    col_teacher = _col("преподаватель", "препод", "фио")
    col_room    = _col("аудитория", "место", "кабинет", "ауд")

    # Если заголовки не найдены, по количеству столбцов: Дата=0, Дисц=1, Преп=2, Место=3
    if col_date is None:    col_date    = 0
    if col_subject is None: col_subject = 1
    if col_teacher is None: col_teacher = 2
    if col_room is None:    col_room    = 3

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

        date_raw     = g(col_date)
        subject_raw  = g(col_subject)
        teacher      = g(col_teacher)
        room         = g(col_room)

        # Пропускаем строку-заголовок
        if not date_raw and not subject_raw:
            continue
        # Строка совпадает с заголовкой
        if date_raw.lower() in headers or subject_raw.lower() in headers:
            continue

        # Форматируем дату и время
        # Формат СГУ: '2026-01-13 13:50:00'
        date_str = date_raw
        time_str = ""
        m_iso = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}:\d{2}))?', date_raw)
        if m_iso:
            date_str = f"{m_iso.group(3)}.{m_iso.group(2)}.{m_iso.group(1)}"
            time_str = m_iso.group(4) or ""
        else:
            # Другие форматы: '13.01.2026 13:50' или просто 'дд.мм'
            m_time = re.search(r'(\d{1,2}:\d{2})', date_raw)
            if m_time:
                time_str = m_time.group(1)
                date_str = date_raw[:m_time.start()].strip()

        # Разделяем дисциплину и тип события
        # Пример: "Микроэкономика Экзамен" → subject="Микроэкономика", kind="Экзамен"
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
        return "📭 Расписание сессии пока не опубликовано."

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
