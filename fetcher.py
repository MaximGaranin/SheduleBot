import logging
import httpx
from database import get_cached_schedule, save_cached_schedule

logger = logging.getLogger(__name__)


async def fetch_page(url: str, use_cache: bool = True) -> str | None:
    """Fetch URL; use SQLite schedule cache when use_cache=True."""
    if use_cache:
        cached = get_cached_schedule(url)
        if cached:
            logger.debug(f"Cache hit: {url}")
            return cached

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; SGU-TG-Bot/1.0)"}
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                html = r.text
                if use_cache:
                    save_cached_schedule(url, html)
                return html
    except Exception as e:
        logger.error(f"fetch error {url}: {e}")

    return None
