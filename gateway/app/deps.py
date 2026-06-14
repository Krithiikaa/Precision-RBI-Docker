from fastapi import Request, HTTPException
from .services import auth


async def current_identity(request: Request) -> dict:
    """Resolve the user from the access cookie; fall back to refresh silently."""
    at = request.cookies.get("rbi_access")
    claims = auth.decode(at) if at else None
    if claims and claims.get("type") == "access":
        return {"user_id": claims["sub"], "sid": claims["sid"]}

    # try silent refresh
    rt = request.cookies.get("rbi_refresh")
    new_access = auth.refresh_access(rt) if rt else None
    if new_access:
        claims = auth.decode(new_access)
        return {"user_id": claims["sub"], "sid": claims["sid"], "_new_access": new_access}

    raise HTTPException(401, "not authenticated")
