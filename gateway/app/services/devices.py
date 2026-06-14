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


async def mark_device(ip: str, user_id: str):
    """Captive portal calls this after a successful one-time login.
    The device (by IP) is then authenticated and never prompted again
    until the TTL expires."""
    data = {"user_id": user_id, "since": int(time.time())}
    await _client().set(f"dev:{ip}", json.dumps(data), ex=settings.REFRESH_TTL)


async def get_device(ip: str) -> dict | None:
    raw = await _client().get(f"dev:{ip}")
    return json.loads(raw) if raw else None


async def forget_device(ip: str):
    await _client().delete(f"dev:{ip}")
