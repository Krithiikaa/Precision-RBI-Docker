import asyncio
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..config import settings

router = APIRouter(tags=["stream"])


@router.websocket("/streamproxy/{browser_id}")
async def stream_proxy(ws: WebSocket, browser_id: str):
    """Relay the viewer's stream WS to the browser-host's /stream endpoint.
    Keeps the browser-host private (not exposed to the user's browser)."""
    await ws.accept()
    backend = settings.BROWSER_HOST_URL.replace("http://", "ws://").replace("https://", "wss://")
    target = f"{backend}/stream/{browser_id}"

    try:
        async with websockets.connect(target, max_size=None) as upstream:

            async def c2s():
                try:
                    while True:
                        msg = await ws.receive_text()
                        await upstream.send(msg)
                except (WebSocketDisconnect, RuntimeError):
                    pass

            async def s2c():
                try:
                    async for msg in upstream:
                        await ws.send_text(msg)
                except Exception:
                    pass

            await asyncio.gather(c2s(), s2c())
    except Exception:
        await ws.close()
