import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services import auth, sessions, audit
from ..services.browser_client import browser_client

router = APIRouter(tags=["session"])


@router.websocket("/ws")
async def session_ws(ws: WebSocket):
    """The single control channel. The user's address-bar input and clicks
    arrive here as nav intents; the URL is resolved ONLY on the server."""
    await ws.accept()

    # auth from cookie sent during WS handshake
    at = ws.cookies.get("rbi_access")
    claims = auth.decode(at) if at else None
    if not claims:
        rt = ws.cookies.get("rbi_refresh")
        new = auth.refresh_access(rt) if rt else None
        claims = auth.decode(new) if new else None
    if not claims:
        await ws.close(code=4401)
        return

    user_id, sid = claims["sub"], claims["sid"]

    # lease an isolated browser for this session
    lease = await browser_client.lease(sid)
    browser_id = lease["browser_id"]
    await sessions.attach_browser(sid, browser_id)
    await audit.emit(user_id, sid, "session_start", meta={"browser_id": browser_id})
    await ws.send_json({"type": "ready", "browser_id": browser_id})

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")

            if mtype == "navigate":
                url = msg.get("url", "").strip()
                if not url:
                    continue
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                await audit.emit(user_id, sid, "nav", url=url)
                # SERVER fetches + renders. User device never touches the site.
                result = await browser_client.navigate(browser_id, url)
                await audit.emit(user_id, sid, "nav_result", url=result.get("final_url", url),
                                 meta={"mode": result.get("mode"), "status": result.get("status")})
                await ws.send_json({"type": "render", **result})

            elif mtype == "action":
                # clicks / keystrokes / scroll captured for logs
                await audit.emit(user_id, sid, "user_action", meta=msg.get("data", {}))

            elif mtype == "ping":
                await ws.send_json({"type": "pong"})

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await audit.emit(user_id, sid, "session_end", meta={"browser_id": browser_id})
        # destroy the disposable browser so NO state persists between users
        await browser_client.release(browser_id)
