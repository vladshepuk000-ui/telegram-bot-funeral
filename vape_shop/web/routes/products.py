import os
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import aiosqlite
from web.auth_utils import verify_session

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")

CATEGORIES = {
    "liquids":    "Рідини",
    "cartridges": "Картриджі",
    "systems":    "Системи (поди)",
}

router = APIRouter(prefix="/products")


@router.get("", response_class=HTMLResponse)
async def products_list(request: Request, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM products ORDER BY is_active DESC, category, name"
        ) as cur:
            products = await cur.fetchall()

    return templates.TemplateResponse(request, "products.html", {
        "products": products,
        "categories": CATEGORIES,
    })


@router.post("/{product_id}/edit")
async def edit_product(
    product_id: int,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    stock: int = Form(...),
    session: str = Depends(verify_session),
):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE products SET name=?, description=?, price=?, stock=? WHERE id=?",
            (name, description, price, stock, product_id)
        )
        await db.commit()

    return RedirectResponse(url="/products", status_code=302)


@router.post("/{product_id}/toggle")
async def toggle_product(product_id: int, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE products SET is_active = NOT is_active WHERE id = ?", (product_id,)
        )
        await db.commit()

    return RedirectResponse(url="/products", status_code=302)


@router.post("/{product_id}/restock")
async def restock_product(product_id: int, quantity: int = Form(...), session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id)
        )
        await db.commit()

    return RedirectResponse(url="/products", status_code=302)
