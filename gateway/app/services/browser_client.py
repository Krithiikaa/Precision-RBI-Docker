import httpx
from ..config import settings


class BrowserClient:
    """Talks to the browser-host control API (Server B)."""

    def __init__(self):
        self.base = settings.BROWSER_HOST_URL

    async def lease(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self.base}/lease", json={"session_id": session_id})
            r.raise_for_status()
            return r.json()   # {browser_id}

    async def release(self, browser_id: str):
        async with httpx.AsyncClient(timeout=30) as c:
            await c.post(f"{self.base}/release", json={"browser_id": browser_id})

    async def navigate(self, browser_id: str, url: str) -> dict:
        """Server-side fetch + render. Returns {mode, content|stream_url, final_url, status}."""
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{self.base}/navigate",
                             json={"browser_id": browser_id, "url": url})
            r.raise_for_status()
            return r.json()


browser_client = BrowserClient()
