from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routers import auth_router, session_router, portal_router, stream_router
from .services import audit


@asynccontextmanager
async def lifespan(app: FastAPI):
    audit.start_worker()
    yield


app = FastAPI(title="Precision-RBI Gateway", lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(session_router.router)
app.include_router(portal_router.router)
app.include_router(stream_router.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.post("/log")
async def log_event(request: Request):
    """The MITM proxy posts every intercepted request here so EVERY URL
    the user visits is captured, per user/device."""
    body = await request.json()
    await audit.emit(
        user_id=body.get("user_id", "unknown"),
        session_id=body.get("ip", ""),
        event_type=body.get("event_type", "proxy_request"),
        url=body.get("url", ""),
        meta=body.get("meta", {}),
    )
    return {"ok": True}


# Serve the thin client SPA
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def index():
    return FileResponse("app/static/index.html")
