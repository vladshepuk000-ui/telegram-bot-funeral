import os
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import aiosqlite
from web.auth_utils import verify_session

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")

STATUS_MAP = {
    "awaiting_payment": "Очікує оплати",
    "new":              "Нове",
    "confirmed":        "Підтверджено",
    "sent":             "Відправлено",
    "done":             "Виконано",
    "cancelled":        "Скасовано",
}

router = APIRouter(prefix="/orders")


@router.get("", response_class=HTMLResponse)
async def orders_list(request: Request, status: str = "", session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        if status and status in STATUS_MAP:
            query = """
                SELECT o.id, o.status, o.total_price, o.created_at, o.address, o.phone,
                       c.username, c.telegram_id
                FROM orders o LEFT JOIN customers c ON o.customer_id = c.id
                WHERE o.status = ?
                ORDER BY o.created_at DESC
            """
            async with db.execute(query, (status,)) as cur:
                orders = await cur.fetchall()
        else:
            query = """
                SELECT o.id, o.status, o.total_price, o.created_at, o.address, o.phone,
                       c.username, c.telegram_id
                FROM orders o LEFT JOIN customers c ON o.customer_id = c.id
                ORDER BY o.created_at DESC
            """
            async with db.execute(query) as cur:
                orders = await cur.fetchall()

    return templates.TemplateResponse(request, "orders.html", {
        "orders": orders,
        "status_map": STATUS_MAP,
        "current_status": status,
    })


@router.get("/{order_id}", response_class=HTMLResponse)
async def order_detail(request: Request, order_id: int, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT o.*, c.username, c.telegram_id, c.phone as customer_phone
            FROM orders o LEFT JOIN customers c ON o.customer_id = c.id
            WHERE o.id = ?
        """, (order_id,)) as cur:
            order = await cur.fetchone()

        if not order:
            return RedirectResponse(url="/orders")

        async with db.execute("""
            SELECT oi.quantity, oi.price_at_order, p.name
            FROM order_items oi LEFT JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        """, (order_id,)) as cur:
            items = await cur.fetchall()

    return templates.TemplateResponse(request, "order_detail.html", {
        "order": order,
        "items": items,
        "status_map": STATUS_MAP,
    })


@router.post("/{order_id}/status")
async def update_status(order_id: int, new_status: str = Form(...), session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    if new_status not in STATUS_MAP:
        return RedirectResponse(url=f"/orders/{order_id}")

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        await db.commit()

    return RedirectResponse(url=f"/orders/{order_id}", status_code=302)
