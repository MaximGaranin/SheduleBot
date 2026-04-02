import re
from bs4 import BeautifulSoup
from config import DAY_NAMES, DAY_EMOJI, DAYS_ORDER, BASE_URL


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def parse_schedule_html(html: str, only_day: str = None) -> str:
    """
    Parse SGU timetable HTML table.
    only_day: short day name e.g. "Пн" — returns only that day.
    """
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

    # Find header row with day names
    day_col = {}
    header_row_idx = None
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

    if not day_col:
        return "⚠️ Не удалось определить структуру таблицы."

    # Skip possible second header row (Пн/Вт/Ср abbreviations)
    data_start = header_row_idx + 1
    if data_start < len(rows):
        next_cells = rows[data_start].find_all(["td", "th"])
        next_texts = [clean(c.get_text()) for c in next_cells]
        if any(t in DAY_NAMES for t in next_texts):
            data_start += 1

    schedule = {day: [] for day in DAYS_ORDER}
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
            parts = re.split(r'(?=ЛЕКЦИЯ|ПРАКТИКА|СЕМИНАР)', lesson)
            for part in parts:
                part = part.strip()
                if part:
                    lines.append(f"     {part}")

    return "\n".join(lines) if lines else "⚠️ Занятий не найдено."


def search_teachers(html: str, query: str) -> list[dict]:
    """Search teacher links on the main schedule page."""
    soup = BeautifulSoup(html, "html.parser")
    query_lower = query.lower()
    results = []
    seen_urls = set()
    for a in soup.find_all("a"):
        link_text = clean(a.get_text())
        href = a.get("href", "")
        if (query_lower in link_text.lower()
                and len(link_text) > 3
                and "/schedule/" in href):
            full_url = BASE_URL + href if href.startswith("/") else href
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                results.append({"name": link_text, "url": full_url})
    return results
