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

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        total_orders = await conn.fetchval("SELECT COUNT(*) FROM orders")
        new_orders = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'new'")
        revenue = await conn.fetchval(
            "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status = 'done'"
        )
        total_customers = await conn.fetchval("SELECT COUNT(*) FROM customers")
        active_products = await conn.fetchval("SELECT COUNT(*) FROM products WHERE is_active = TRUE")
        out_of_stock = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE is_active = TRUE AND stock = 0"
        )
        recent_orders = await conn.fetch("""
            SELECT o.id, o.status, o.total_price, o.created_at,
                   c.username, c.telegram_id
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            ORDER BY o.created_at DESC LIMIT 5
        """)
    finally:
        await conn.close()

    return templates.TemplateResponse(request, "dashboard.html", {
        "total_orders": total_orders,
        "new_orders": new_orders,
        "revenue": revenue,
        "total_customers": total_customers,
        "active_products": active_products,
        "out_of_stock": out_of_stock,
        "recent_orders": recent_orders,
    })
