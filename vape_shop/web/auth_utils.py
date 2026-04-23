import os
import hashlib
from fastapi import Cookie, HTTPException
from typing import Optional

ADMIN_PASSWORD = os.getenv("ADMIN_WEB_PASSWORD", "admin123")
SESSION_TOKEN = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()


def verify_session(session: Optional[str] = Cookie(default=None)) -> bool:
    return session == SESSION_TOKEN


def require_auth(session: Optional[str] = Cookie(default=None)):
    from fastapi.responses import RedirectResponse
    if session != SESSION_TOKEN:
        return RedirectResponse(url="/login", status_code=302)
    return True
