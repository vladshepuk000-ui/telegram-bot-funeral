import os
import asyncpg
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web.auth_utils import verify_session

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"
)

router = APIRouter(prefix="/customers")


@router.get("", response_class=HTMLResponse)
async def customers_list(request: Request, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        customers = await conn.fetch("""
            SELECT c.*,
                   COUNT(o.id) as orders_count,
                   COALESCE(SUM(o.total_price), 0) as total_spent
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id AND o.status = 'done'
            GROUP BY c.id
            ORDER BY c.first_seen DESC
        """)
    finally:
        await conn.close()

    return templates.TemplateResponse(request, "customers.html", {
        "customers": customers,
    })
