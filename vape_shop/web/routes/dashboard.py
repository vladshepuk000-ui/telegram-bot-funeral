import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import aiosqlite
from web.auth_utils import verify_session

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT COUNT(*) as cnt FROM orders") as cur:
            total_orders = (await cur.fetchone())["cnt"]

        async with db.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'new'") as cur:
            new_orders = (await cur.fetchone())["cnt"]

        async with db.execute("SELECT COALESCE(SUM(total_price), 0) as total FROM orders WHERE status = 'done'") as cur:
            revenue = (await cur.fetchone())["total"]

        async with db.execute("SELECT COUNT(*) as cnt FROM customers") as cur:
            total_customers = (await cur.fetchone())["cnt"]

        async with db.execute("SELECT COUNT(*) as cnt FROM products WHERE is_active = 1") as cur:
            active_products = (await cur.fetchone())["cnt"]

        async with db.execute("SELECT COUNT(*) as cnt FROM products WHERE is_active = 1 AND stock = 0") as cur:
            out_of_stock = (await cur.fetchone())["cnt"]

        async with db.execute("""
            SELECT o.id, o.status, o.total_price, o.created_at,
                   c.username, c.telegram_id
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            ORDER BY o.created_at DESC LIMIT 5
        """) as cur:
            recent_orders = await cur.fetchall()

    return templates.TemplateResponse(request, "dashboard.html", {
        "total_orders": total_orders,
        "new_orders": new_orders,
        "revenue": revenue,
        "total_customers": total_customers,
        "active_products": active_products,
        "out_of_stock": out_of_stock,
        "recent_orders": recent_orders,
    })
