import os
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import aiosqlite
from web.auth_utils import verify_session

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")

router = APIRouter(prefix="/broadcasts")


@router.get("", response_class=HTMLResponse)
async def broadcasts_list(request: Request, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT 20"
        ) as cur:
            history = await cur.fetchall()

        async with db.execute("SELECT COUNT(*) as cnt FROM customers WHERE is_subscribed = 1") as cur:
            subscribers = (await cur.fetchone())["cnt"]

    return templates.TemplateResponse(request, "broadcasts.html", {
        "history": history,
        "subscribers": subscribers,
    })
