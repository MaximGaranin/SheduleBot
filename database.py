import sqlite3
import logging
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sgu_bot.db"
logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id     INTEGER PRIMARY KEY,
                faculty     TEXT    NOT NULL,
                form        TEXT    NOT NULL,
                grp         TEXT    NOT NULL,
                updated_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS teacher_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                query       TEXT    NOT NULL,
                name        TEXT    NOT NULL,
                url         TEXT    NOT NULL,
                fetched_at  TEXT    DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_teacher_query ON teacher_cache (query);

            CREATE TABLE IF NOT EXISTS schedule_cache (
                cache_key   TEXT    PRIMARY KEY,
                html        TEXT    NOT NULL,
                fetched_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                search_type TEXT    NOT NULL,
                query       TEXT    NOT NULL,
                searched_at TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS favorites (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                fav_type    TEXT    NOT NULL,
                label       TEXT    NOT NULL,
                faculty     TEXT,
                form        TEXT,
                grp         TEXT,
                teacher_url TEXT,
                teacher_name TEXT,
                added_at    TEXT    DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_fav_unique
                ON favorites (user_id, fav_type, label);

            CREATE TABLE IF NOT EXISTS notify_subscriptions (
                user_id    INTEGER PRIMARY KEY,
                active     INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT    DEFAULT (datetime('now'))
            );
        """)
    logger.info(f"Database initialised at {DB_PATH}")


# ─── Profiles ────────────────────────────────────────────────────────────

def get_profile(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT faculty, form, grp FROM profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()
    return dict(row) if row else None


def save_profile(user_id: int, faculty: str, form: str, group: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO profiles (user_id, faculty, form, grp, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                faculty = excluded.faculty, form = excluded.form,
                grp = excluded.grp, updated_at = excluded.updated_at
        """, (user_id, faculty, form, group))


def delete_profile(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))


# ─── Teacher cache ────────────────────────────────────────────────────────

TEACHER_CACHE_TTL_HOURS = 6


def get_cached_teachers(query: str) -> list[dict] | None:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT name, url FROM teacher_cache
            WHERE query = ?
              AND fetched_at > datetime('now', ? || ' hours')
            ORDER BY id
        """, (query.lower(), f"-{TEACHER_CACHE_TTL_HOURS}")).fetchall()
    return [dict(r) for r in rows] if rows else None


def save_cached_teachers(query: str, teachers: list[dict]):
    with get_conn() as conn:
        conn.execute("DELETE FROM teacher_cache WHERE query = ?", (query.lower(),))
        conn.executemany(
            "INSERT INTO teacher_cache (query, name, url) VALUES (?, ?, ?)",
            [(query.lower(), t["name"], t["url"]) for t in teachers]
        )


# ─── Schedule HTML cache ─────────────────────────────────────────────────

SCHEDULE_CACHE_TTL_HOURS = 1


def get_cached_schedule(cache_key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT html FROM schedule_cache
            WHERE cache_key = ?
              AND fetched_at > datetime('now', ? || ' hours')
        """, (cache_key, f"-{SCHEDULE_CACHE_TTL_HOURS}")).fetchone()
    return row["html"] if row else None


def save_cached_schedule(cache_key: str, html: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO schedule_cache (cache_key, html, fetched_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(cache_key) DO UPDATE SET
                html = excluded.html, fetched_at = excluded.fetched_at
        """, (cache_key, html))


# ─── Search history ───────────────────────────────────────────────────────

def add_history(user_id: int, search_type: str, query: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO search_history (user_id, search_type, query) VALUES (?, ?, ?)",
            (user_id, search_type, query)
        )


def get_history(user_id: int, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT search_type, query, searched_at FROM search_history
            WHERE user_id = ? ORDER BY searched_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ─── Favorites ────────────────────────────────────────────────────────────

MAX_FAVORITES = 20


def get_favorites(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM favorites WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def add_favorite_group(
    user_id: int, label: str,
    faculty: str, form: str, grp: str
) -> bool:
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        if count >= MAX_FAVORITES:
            return False
        try:
            conn.execute("""
                INSERT INTO favorites (user_id, fav_type, label, faculty, form, grp)
                VALUES (?, 'group', ?, ?, ?, ?)
            """, (user_id, label, faculty, form, grp))
            return True
        except Exception:
            return False


def add_favorite_teacher(
    user_id: int, label: str,
    teacher_name: str, teacher_url: str
) -> bool:
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        if count >= MAX_FAVORITES:
            return False
        try:
            conn.execute("""
                INSERT INTO favorites
                    (user_id, fav_type, label, teacher_name, teacher_url)
                VALUES (?, 'teacher', ?, ?, ?)
            """, (user_id, label, teacher_name, teacher_url))
            return True
        except Exception:
            return False


def delete_favorite(user_id: int, fav_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM favorites WHERE id = ? AND user_id = ?",
            (fav_id, user_id)
        )


def get_favorite_by_id(fav_id: int, user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM favorites WHERE id = ? AND user_id = ?",
            (fav_id, user_id)
        ).fetchone()
    return dict(row) if row else None


# ─── Notify subscriptions ─────────────────────────────────────────────────

def is_notify_subscribed(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT active FROM notify_subscriptions WHERE user_id = ?",
            (user_id,)
        ).fetchone()
    return bool(row and row["active"])


def set_notify_subscription(user_id: int, active: bool):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO notify_subscriptions (user_id, active, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                active = excluded.active,
                updated_at = excluded.updated_at
        """, (user_id, int(active)))


def get_notify_subscribers() -> list[int]:
    """Return all user_ids with active notifications."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id FROM notify_subscriptions WHERE active = 1"
        ).fetchall()
    return [r["user_id"] for r in rows]
