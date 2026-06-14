import asyncio
import base64
import json
import uuid
from urllib.parse import urlparse
import bleach
from bleach.css_sanitizer import CSSSanitizer
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from playwright.async_api import async_playwright

app = FastAPI(title="Precision-RBI Browser Host")

_pw = None
_browser = None
_contexts: dict[str, dict] = {}   # browser_id -> {context, page}

# tags considered "complex" -> force pixel fallback for stronger isolation
PIXEL_TRIGGER_TAGS = ("<canvas", "<video", "<embed", "<object")

ALLOWED_TAGS = list(bleach.sanitizer.ALLOWED_TAGS) + [
    "p","div","span","img","h1","h2","h3","h4","h5","h6","br","hr",
    "table","thead","tbody","tr","td","th","ul","ol","li","a","strong","em",
    "section","article","header","footer","nav","main","figure","figcaption","pre","code",
]
ALLOWED_ATTRS = {"*": ["class","id","style","href","src","alt","title"]}

_css = CSSSanitizer(allowed_css_properties=[
    "color","background","background-color","font-size","font-weight",
    "font-family","text-align","margin","padding","border","width","height",
    "display","float","line-height",
])


def _origin(u: str) -> str:
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}/"


@app.on_event("startup")
async def startup():
    global _pw, _browser
    _pw = await async_playwright().start()
    _browser = await _pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )


@app.on_event("shutdown")
async def shutdown():
    if _browser: await _browser.close()
    if _pw: await _pw.stop()


class LeaseBody(BaseModel):
    session_id: str

class ReleaseBody(BaseModel):
    browser_id: str

class NavBody(BaseModel):
    browser_id: str
    url: str


@app.post("/lease")
async def lease(body: LeaseBody):
    """Fresh, isolated context per session — destroyed on release."""
    bid = "br_" + uuid.uuid4().hex[:10]
    ctx = await _browser.new_context(
        record_har_path=f"/tmp/{bid}.har",   # full network log per session
        ignore_https_errors=True,
        viewport={"width": 1280, "height": 800},
    )
    page = await ctx.new_page()
    _contexts[bid] = {"context": ctx, "page": page}
    return {"browser_id": bid}


@app.post("/release")
async def release(body: ReleaseBody):
    entry = _contexts.pop(body.browser_id, None)
    if entry:
        await entry["context"].close()   # discards all state, cookies, cache
    return {"ok": True}


@app.post("/navigate")
async def navigate(body: NavBody):
    entry = _contexts.get(body.browser_id)
    if not entry:
        raise HTTPException(404, "no such browser")
    page = entry["page"]

    resp = await page.goto(body.url, wait_until="domcontentloaded", timeout=30000)
    final_url = page.url
    status = resp.status if resp else 0
    html = await page.content()

    # decide DOM-mirror vs pixel fallback
    low = html.lower()
    needs_pixel = any(t in low for t in PIXEL_TRIGGER_TAGS) or len(html) > 2_000_000

    if needs_pixel:
        png = await page.screenshot(full_page=False)
        data_uri = "data:image/png;base64," + base64.b64encode(png).decode()
        return {"mode": "pixel", "content": data_uri,
                "final_url": final_url, "status": status}

    # DOM-mirror: sanitize before it ever reaches the user
    safe = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                        css_sanitizer=_css, strip=True)
    # resolve relative URLs (/logos/foo.gif) against the real origin
    safe = f'<base href="{_origin(final_url)}">' + safe
    return {"mode": "dom", "content": safe,
            "final_url": final_url, "status": status}


# ───────────────────────── Pixel streaming ─────────────────────────
# CDP screencast pushes JPEG frames as the page changes; we forward them
# to the viewer over WebSocket and dispatch the viewer's input back.

@app.websocket("/stream/{browser_id}")
async def stream(ws: WebSocket, browser_id: str):
    await ws.accept()
    entry = _contexts.get(browser_id)
    if not entry:
        await ws.close(code=4404)
        return
    page = entry["page"]
    cdp = await entry["context"].new_cdp_session(page)

    async def on_frame(params):
        # send frame to viewer, then ack so CDP keeps sending
        try:
            await ws.send_text(json.dumps({"type": "frame", "data": params["data"]}))
            await cdp.send("Page.screencastFrameAck",
                           {"sessionId": params["sessionId"]})
        except Exception:
            pass

    cdp.on("Page.screencastFrame", lambda p: asyncio.create_task(on_frame(p)))
    await cdp.send("Page.startScreencast",
                   {"format": "jpeg", "quality": 50,
                    "maxWidth": 1280, "maxHeight": 720, "everyNthFrame": 2})

    try:
        while True:
            msg = json.loads(await ws.receive_text())
            t = msg.get("type")
            if t == "navigate":
                url = msg["url"]
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            elif t == "mouse":
                await cdp.send("Input.dispatchMouseEvent", {
                    "type": msg["action"],           # mousePressed/Released/Moved/mouseWheel
                    "x": msg["x"], "y": msg["y"],
                    "button": msg.get("button", "left"),
                    "clickCount": msg.get("clickCount", 1),
                    "deltaX": msg.get("deltaX", 0), "deltaY": msg.get("deltaY", 0),
                })
            elif t == "key":
                await cdp.send("Input.dispatchKeyEvent", {
                    "type": msg["action"],           # keyDown/keyUp/char
                    "text": msg.get("text", ""),
                    "key": msg.get("key", ""),
                    "code": msg.get("code", ""),
                })
            elif t == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        try:
            await cdp.send("Page.stopScreencast")
        except Exception:
            pass
