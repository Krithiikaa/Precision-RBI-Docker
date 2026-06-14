import json
import time
import asyncio
import httpx
from ..config import settings

_queue: asyncio.Queue = asyncio.Queue()


async def emit(user_id: str, session_id: str, event_type: str,
               url: str = "", meta: dict | None = None):
    """Enqueue an audit event. Captures EVERY user action / navigation."""
    await _queue.put({
        "ts": time.time(),
        "user_id": user_id,
        "session_id": session_id,
        "event_type": event_type,
        "url": url,
        "meta": json.dumps(meta or {}),
    })


async def _flush_loop():
    """Background worker: batch-insert events into ClickHouse."""
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            batch = []
            try:
                first = await _queue.get()
                batch.append(first)
                # drain up to 200 quickly
                for _ in range(199):
                    try:
                        batch.append(_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
            except Exception:
                await asyncio.sleep(1)
                continue

            rows = "\n".join(json.dumps(e) for e in batch)
            try:
                await client.post(
                    f"{settings.CLICKHOUSE_URL}/?query="
                    f"INSERT INTO {settings.CLICKHOUSE_DB}.audit FORMAT JSONEachRow",
                    content=rows,
                )
            except Exception:
                # In a real deploy, write to a local WAL/file fallback here.
                for e in batch:
                    print("[AUDIT-FALLBACK]", e)
            await asyncio.sleep(0.5)


def start_worker():
    asyncio.create_task(_flush_loop())
