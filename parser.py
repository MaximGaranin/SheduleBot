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

_SESSION_TYPES = {
    "экзамен":                  "📝",
    "зачет":                    "✅",
    "зачёт":                    "✅",
    "консультация":             "💬",
    "дифференцированный зачет": "📊",
    "диф. зачет":               "📊",
    "диф.зачет":                "📊",
    "курсовая":                 "📐",
}


def _event_emoji(text: str) -> str:
    low = text.lower()
    for key, emoji in _SESSION_TYPES.items():
        if key in low:
            return emoji
    return "📌"


def parse_session_html(html: str) -> str:
    """Парсит страницу /schedule/{fac}/{form}/{grp}/session СГУ.

    Формат таблицы: Дата | Дисциплина | Преподаватель | Место проведения
    Дата и время могут быть в одной ячейке в форматах:
      - '2026-01-13 13:50:00'
      - '13.01.2026 13:50'
      - '13 января 2026 13:50'
    """
    soup = BeautifulSoup(html, "html.parser")

    # Ищем таблицу с нужными столбцами
    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if ("Дисциплина" in text or "дисциплин" in text.lower()) and \
           ("Преподаватель" in text or "препод" in text.lower() or "Дата" in text):
            target_table = table
            break

    # Фолбэк: любая таблица с датами в строках
    if not target_table:
        for table in soup.find_all("table"):
            text = table.get_text()
            if re.search(r'\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}', text):
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

    # Определяем заголовки
    header_cells = rows[0].find_all(["td", "th"])
    headers = [clean(c.get_text()).lower() for c in header_cells]

    def _col(*keywords):
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return None

    col_date    = _col("дата", "число")
    col_time    = _col("время", "час")
    col_subject = _col("дисциплин", "предмет", "название")
    col_type    = _col("вид", "тип", "форма")
    col_teacher = _col("преподаватель", "препод", "фио")
    col_room    = _col("аудитория", "кабинет", "ауд", "место")

    # Если в дате уже есть время (нет отдельной колонки времени),
    # попробуем определить это после первой строки данных
    date_has_time = False

    entries = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [clean(c.get_text(" ")) for c in cells]

        # Пропускаем строки-заголовки внутри таблицы
        if all(t.lower() in headers or not t for t in texts):
            continue

        def g(idx):
            if idx is not None and idx < len(texts):
                v = texts[idx]
                return v if v not in ("-", "–", "—") else ""
            return ""

        date_raw = g(col_date)
        time_val = g(col_time)
        subject  = g(col_subject)
        kind     = g(col_type)
        teacher  = g(col_teacher)
        room     = g(col_room)

        # Если нет отдельной колонки даты — ищем дату по содержимому
        if col_date is None:
            for t in texts:
                if re.search(r'\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}', t):
                    date_raw = t
                    break

        # Если нет отдельной колонки времени — извлекаем время из даты
        if col_time is None and date_raw:
            m = re.search(r'(\d{1,2}:\d{2})(?::\d{2})?', date_raw)
            if m:
                time_val = m.group(1)
                date_has_time = True

        # Форматируем дату
        date_str = date_raw
        # ISO формат: 2026-01-13 13:50:00 → 13.01.2026
        m_iso = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_raw)
        if m_iso:
            date_str = f"{m_iso.group(3)}.{m_iso.group(2)}.{m_iso.group(1)}"
            if not time_val:
                mt = re.search(r'(\d{2}:\d{2})(?::\d{2})?', date_raw)
                if mt:
                    time_val = mt.group(1)

        # Если предмет не определён — берём самую длинную ячейку (кроме даты)
        if not subject and len(texts) >= 2:
            candidates = [t for i, t in enumerate(texts) if i != col_date]
            subject = max(candidates, key=len, default="")

        # Пропускаем пустые строки
        if not date_str and not subject:
            continue

        emoji = _event_emoji(kind or subject)
        line  = f"{emoji} *{date_str}*"
        if time_val:
            line += f" `{time_val}`"
        if kind and subject and kind.lower() not in subject.lower():
            line += f" — _{kind}_"
        if subject:
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
