from __future__ import annotations

import secrets
import threading
import time

from fastapi import HTTPException, Request, Response

from config import SETTINGS


COOKIE_NAME = "admin_session"
_SESSIONS: dict[str, float] = {}
_LOCK = threading.Lock()


def _cleanup(now: float) -> None:
    expired_tokens = [token for token, expire_at in _SESSIONS.items() if expire_at <= now]
    for token in expired_tokens:
        _SESSIONS.pop(token, None)


def create_session() -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    ttl = SETTINGS.admin_session_ttl_seconds
    expire_at = time.time() + ttl
    with _LOCK:
        _cleanup(time.time())
        _SESSIONS[token] = expire_at
    return token, ttl


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "").strip()
    if not token:
        return False

    now = time.time()
    with _LOCK:
        _cleanup(now)
        expire_at = _SESSIONS.get(token)
        if not expire_at:
            return False
        if expire_at <= now:
            _SESSIONS.pop(token, None)
            return False
        return True


def require_admin(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")


def delete_session(token: str) -> None:
    if not token:
        return
    with _LOCK:
        _SESSIONS.pop(token, None)


def set_auth_cookie(response: Response, token: str, ttl: int) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=ttl,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/admin",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/admin")

