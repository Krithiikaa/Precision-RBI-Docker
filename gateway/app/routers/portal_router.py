from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from ..config import settings
from ..services import devices, audit
from ..services.browser_client import browser_client

router = APIRouter(tags=["portal"])


def _client_ip(request: Request) -> str:
    # honor X-Forwarded-For from the proxy if present
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class PortalLogin(BaseModel):
    username: str
    password: str
    client_ip: str | None = None   # proxy passes the real device IP


@router.get("/portal", response_class=HTMLResponse)
async def portal_page():
    return FileResponse("app/static/portal.html")


@router.post("/portal/login")
async def portal_login(body: PortalLogin, request: Request):
    """One-time login. Marks the device (IP) authenticated."""
    expected = settings.DEMO_USERS.get(body.username)
    if not expected or expected != body.password:
        raise HTTPException(401, "invalid credentials")
    ip = body.client_ip or _client_ip(request)
    await devices.mark_device(ip, body.username)
    await audit.emit(body.username, ip, "portal_login", meta={"ip": ip})
    return {"ok": True, "ip": ip}


@router.get("/portal/check")
async def portal_check(ip: str):
    """Called by the proxy to decide: is this device already authenticated?"""
    dev = await devices.get_device(ip)
    if not dev:
        return JSONResponse({"authenticated": False})
    return {"authenticated": True, "user_id": dev["user_id"]}


@router.post("/portal/session")
async def portal_session(request: Request):
    """Proxy asks the gateway to lease an isolated browser for a device."""
    body = await request.json()
    ip = body.get("ip") or _client_ip(request)
    dev = await devices.get_device(ip)
    if not dev:
        raise HTTPException(401, "device not authenticated")
    lease = await browser_client.lease(ip)
    await audit.emit(dev["user_id"], ip, "session_start",
                     meta={"browser_id": lease["browser_id"]})
    return {"browser_id": lease["browser_id"], "user_id": dev["user_id"]}


@router.get("/viewer", response_class=HTMLResponse)
async def viewer():
    return FileResponse("app/static/viewer.html")
