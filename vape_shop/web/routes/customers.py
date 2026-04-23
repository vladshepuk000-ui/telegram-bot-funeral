import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import aiosqlite
from web.auth_utils import verify_session

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")

router = APIRouter(prefix="/customers")


@router.get("", response_class=HTMLResponse)
async def customers_list(request: Request, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT c.*,
                   COUNT(o.id) as orders_count,
                   COALESCE(SUM(o.total_price), 0) as total_spent
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id AND o.status = 'done'
            GROUP BY c.id
            ORDER BY c.first_seen DESC
        """) as cur:
            customers = await cur.fetchall()

    return templates.TemplateResponse(request, "customers.html", {
        "customers": customers,
    })
