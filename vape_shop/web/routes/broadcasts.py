import os
import asyncpg
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web.auth_utils import verify_session

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"
)

router = APIRouter(prefix="/broadcasts")


@router.get("", response_class=HTMLResponse)
async def broadcasts_list(request: Request, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        history = await conn.fetch(
            "SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT 20"
        )
        subscribers = await conn.fetchval(
            "SELECT COUNT(*) FROM customers WHERE is_subscribed = TRUE"
        )
    finally:
        await conn.close()

    return templates.TemplateResponse(request, "broadcasts.html", {
        "history": history,
        "subscribers": subscribers,
    })
