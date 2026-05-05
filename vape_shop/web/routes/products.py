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

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        products = await conn.fetch(
            "SELECT * FROM products ORDER BY is_active DESC, category, name"
        )
    finally:
        await conn.close()

    return templates.TemplateResponse(request, "products.html", {
        "products": products,
        "categories": CATEGORIES,
    })


@router.post("/add")
async def add_product(
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form("liquids"),
    price: float = Form(...),
    old_price: str = Form(""),
    stock: int = Form(...),
    session: str = Depends(verify_session),
):
    if not session:
        return RedirectResponse(url="/login")

    try:
        old_price_val = float(old_price) if old_price.strip() else None
    except ValueError:
        old_price_val = None

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO products (name, description, category, price, old_price, stock, is_active) VALUES ($1, $2, $3, $4, $5, $6, TRUE)",
            name, description, category, price, old_price_val, stock
        )
    finally:
        await conn.close()

    return RedirectResponse(url="/products", status_code=302)


@router.post("/{product_id}/edit")
async def edit_product(
    product_id: int,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    stock: int = Form(...),
    old_price: str = Form(""),
    is_new: str = Form(""),
    is_hit: str = Form(""),
    session: str = Depends(verify_session),
):
    if not session:
        return RedirectResponse(url="/login")

    try:
        old_price_val = float(old_price) if old_price.strip() else None
    except ValueError:
        old_price_val = None

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "UPDATE products SET name=$1, description=$2, price=$3, stock=$4, old_price=$5, is_new=$6, is_hit=$7 WHERE id=$8",
            name, description, price, stock, old_price_val,
            1 if is_new else 0, 1 if is_hit else 0, product_id
        )
    finally:
        await conn.close()

    return RedirectResponse(url="/products", status_code=302)


@router.post("/{product_id}/toggle")
async def toggle_product(product_id: int, session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "UPDATE products SET is_active = NOT is_active WHERE id = $1", product_id
        )
    finally:
        await conn.close()

    return RedirectResponse(url="/products", status_code=302)


@router.post("/{product_id}/restock")
async def restock_product(product_id: int, quantity: int = Form(...), session: str = Depends(verify_session)):
    if not session:
        return RedirectResponse(url="/login")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "UPDATE products SET stock = stock + $1 WHERE id = $2", quantity, product_id
        )
    finally:
        await conn.close()

    return RedirectResponse(url="/products", status_code=302)
