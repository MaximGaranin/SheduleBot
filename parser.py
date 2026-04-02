import re
from bs4 import BeautifulSoup
from config import DAY_NAMES, DAY_EMOJI, DAYS_ORDER, BASE_URL


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _parse_horizontal(rows, header_row_idx) -> dict:
    """Горизонтальная таблица: дни = столбцы (расписание группы)."""
    day_col = {}
    for row in rows[:header_row_idx + 1]:
        cells = row.find_all(["td", "th"])
        for c_idx, cell in enumerate(cells):
            txt = clean(cell.get_text())
            short = DAY_NAMES.get(txt)
            if short:
                day_col[c_idx] = short

    schedule = {day: [] for day in DAYS_ORDER}
    data_start = header_row_idx + 1
    # Пропустить возможную вторую строку заголовка
    if data_start < len(rows):
        next_cells = rows[data_start].find_all(["td", "th"])
        next_texts = [clean(c.get_text()) for c in next_cells]
        if any(t in DAY_NAMES for t in next_texts):
            data_start += 1

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
    """Вертикальная таблица: дни = строки (расписание преподавателя).

    Структура каждой строки-блока:
      [0] номер дня / название дня
      [1] время
      [2] содержимое занятия
    Или строка-заголовок дня, за которой идут строки времён.
    """
    schedule = {day: [] for day in DAYS_ORDER}
    current_day = None

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [clean(c.get_text(" ")) for c in cells]

        # Строка-заголовок дня: одна ячейка = название дня
        if len(texts) == 1:
            short = DAY_NAMES.get(texts[0])
            if short:
                current_day = short
            continue

        # Проверяем, не начинается ли первая ячейка с названия дня
        first_short = DAY_NAMES.get(texts[0])
        if first_short:
            current_day = first_short
            texts = texts[1:]  # остаток строки — время и занятие

        if current_day is None:
            continue

        # Ищем время в любой из ячеек
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
                return f"📭 В *{day}* занятий нет."
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

    # Определяем тип таблицы: горизонтальная или вертикальная
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
        # Горизонтальная: дни в первых строках как столбцы
        schedule = _parse_horizontal(rows, header_row_idx)
    else:
        # Вертикальная: дни как строки (преподаватели)
        schedule = _parse_vertical(rows)

    return _format_schedule(schedule, only_day)


# ─── Поиск преподавателей ──────────────────────────────────────────────────────

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
