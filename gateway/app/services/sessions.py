import json
import time
import redis.asyncio as redis
from ..config import settings

_r: redis.Redis | None = None


def _client() -> redis.Redis:
    global _r
    if _r is None:
        _r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _r


async def save_session(sid: str, user_id: str, browser_id: str | None = None):
    data = {
        "user_id": user_id,
        "browser_id": browser_id or "",
        "created": int(time.time()),
        "last_seen": int(time.time()),
    }
    await _client().set(f"sess:{sid}", json.dumps(data), ex=settings.REFRESH_TTL)


async def get_session(sid: str) -> dict | None:
    raw = await _client().get(f"sess:{sid}")
    return json.loads(raw) if raw else None


async def attach_browser(sid: str, browser_id: str):
    sess = await get_session(sid)
    if sess:
        sess["browser_id"] = browser_id
        sess["last_seen"] = int(time.time())
        await _client().set(f"sess:{sid}", json.dumps(sess), ex=settings.REFRESH_TTL)


async def drop_session(sid: str):
    await _client().delete(f"sess:{sid}")
