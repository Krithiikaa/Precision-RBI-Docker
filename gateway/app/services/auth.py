import time
import uuid
import jwt
from ..config import settings


def _now() -> int:
    return int(time.time())


def issue_tokens(user_id: str) -> dict:
    """Issue an access token (short) + refresh token (long)."""
    sid = str(uuid.uuid4())
    access = jwt.encode(
        {"sub": user_id, "sid": sid, "type": "access",
         "exp": _now() + settings.ACCESS_TTL},
        settings.JWT_SECRET, algorithm=settings.JWT_ALG,
    )
    refresh = jwt.encode(
        {"sub": user_id, "sid": sid, "type": "refresh",
         "exp": _now() + settings.REFRESH_TTL},
        settings.JWT_SECRET, algorithm=settings.JWT_ALG,
    )
    return {"access": access, "refresh": refresh, "sid": sid}


def decode(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except jwt.PyJWTError:
        return None


def refresh_access(refresh_token: str) -> str | None:
    """Silently mint a new access token from a still-valid refresh token.
    This is what gives 'login once per user' — no re-prompt until refresh expires."""
    claims = decode(refresh_token)
    if not claims or claims.get("type") != "refresh":
        return None
    return jwt.encode(
        {"sub": claims["sub"], "sid": claims["sid"], "type": "access",
         "exp": _now() + settings.ACCESS_TTL},
        settings.JWT_SECRET, algorithm=settings.JWT_ALG,
    )
