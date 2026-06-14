from fastapi import APIRouter, Response, Request, HTTPException
from pydantic import BaseModel
from ..services import auth, sessions
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


def _set_cookies(resp: Response, access: str, refresh: str):
    resp.set_cookie("rbi_access", access, httponly=True,
                    secure=settings.COOKIE_SECURE, samesite="lax",
                    max_age=settings.ACCESS_TTL)
    resp.set_cookie("rbi_refresh", refresh, httponly=True,
                    secure=settings.COOKIE_SECURE, samesite="lax",
                    max_age=settings.REFRESH_TTL)


@router.post("/login")
async def login(body: LoginBody, resp: Response):
    expected = settings.DEMO_USERS.get(body.username)
    if not expected or expected != body.password:
        raise HTTPException(401, "invalid credentials")
    tokens = auth.issue_tokens(body.username)
    await sessions.save_session(tokens["sid"], body.username)
    _set_cookies(resp, tokens["access"], tokens["refresh"])
    return {"ok": True, "user": body.username, "sid": tokens["sid"]}


@router.post("/refresh")
async def refresh(request: Request, resp: Response):
    """Silent re-auth: called automatically by the client; user is NOT re-prompted."""
    rt = request.cookies.get("rbi_refresh")
    if not rt:
        raise HTTPException(401, "no refresh token")
    new_access = auth.refresh_access(rt)
    if not new_access:
        raise HTTPException(401, "refresh expired")
    resp.set_cookie("rbi_access", new_access, httponly=True,
                    secure=settings.COOKIE_SECURE, samesite="lax",
                    max_age=settings.ACCESS_TTL)
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, resp: Response):
    at = request.cookies.get("rbi_access")
    claims = auth.decode(at) if at else None
    if claims:
        await sessions.drop_session(claims.get("sid", ""))
    resp.delete_cookie("rbi_access")
    resp.delete_cookie("rbi_refresh")
    return {"ok": True}
