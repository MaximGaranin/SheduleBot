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
    """Create all tables on first run."""
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

            CREATE INDEX IF NOT EXISTS idx_teacher_query
                ON teacher_cache (query);

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
        """)
    logger.info(f"Database initialised at {DB_PATH}")


# ─── Profiles ──────────────────────────────────────────────────────────────

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
                faculty    = excluded.faculty,
                form       = excluded.form,
                grp        = excluded.grp,
                updated_at = excluded.updated_at
        """, (user_id, faculty, form, group))


def delete_profile(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))


# ─── Teacher cache ─────────────────────────────────────────────────────────

TEACHER_CACHE_TTL_HOURS = 6


def get_cached_teachers(query: str) -> list[dict] | None:
    """Return cached teacher list, or None if expired/absent."""
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


# ─── Schedule HTML cache ───────────────────────────────────────────────────

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
                html       = excluded.html,
                fetched_at = excluded.fetched_at
        """, (cache_key, html))


# ─── Search history ────────────────────────────────────────────────────────

def add_history(user_id: int, search_type: str, query: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO search_history (user_id, search_type, query) VALUES (?, ?, ?)",
            (user_id, search_type, query)
        )


def get_history(user_id: int, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT search_type, query, searched_at
            FROM search_history
            WHERE user_id = ?
            ORDER BY searched_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]
