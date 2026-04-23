import os
import aiosqlite
import aiohttp
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=BASE_DIR)
DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")

router = APIRouter()


@router.get("/site", response_class=HTMLResponse)
async def landing(request: Request):
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT r.rating, r.text, r.created_at, c.username
            FROM reviews r
            LEFT JOIN customers c ON r.customer_id = c.id
            WHERE r.text IS NOT NULL AND r.text != ''
            ORDER BY r.created_at DESC
            LIMIT 6
        """) as cur:
            reviews = await cur.fetchall()

        async with db.execute("""
            SELECT COUNT(*) as cnt FROM products WHERE is_active = 1 AND stock > 0
        """) as cur:
            products_count = (await cur.fetchone())["cnt"]

        async with db.execute("""
            SELECT id, name, category, description, price, stock, photo_id
            FROM products WHERE is_active = 1
            ORDER BY category, name
        """) as cur:
            products = await cur.fetchall()

        async with db.execute("SELECT COUNT(*) as cnt FROM customers") as cur:
            customers_count = (await cur.fetchone())["cnt"]

        async with db.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'done'") as cur:
            orders_count = (await cur.fetchone())["cnt"]

    bot_username = os.getenv("BOT_USERNAME", "your_bot")

    return templates.TemplateResponse(request, "site.html", {
        "reviews": reviews,
        "products": products,
        "products_count": products_count,
        "customers_count": customers_count,
        "orders_count": orders_count,
        "bot_username": bot_username,
        "contact_username": os.getenv("CONTACT_USERNAME", "Vlad_shepuk"),
        "contact_phone": os.getenv("CONTACT_PHONE", "+380981256254"),
        "pickup_address": os.getenv("PICKUP_ADDRESS", "Велика Михайлівка"),
    })


@router.get("/api/products-stock")
async def products_stock():
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, stock FROM products WHERE is_active = 1"
        ) as cur:
            rows = await cur.fetchall()
    return JSONResponse([{"id": r["id"], "stock": r["stock"]} for r in rows])


@router.get("/api/product/{product_id}")
async def product_detail(product_id: int):
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, category, description, price, stock, photo_id FROM products WHERE id = ? AND is_active = 1",
            (product_id,)
        ) as cur:
            p = await cur.fetchone()
        if not p:
            return JSONResponse({"error": "not found"}, status_code=404)

        async with db.execute(
            "SELECT photo_id FROM product_photos WHERE product_id = ? ORDER BY position",
            (product_id,)
        ) as cur:
            photo_rows = await cur.fetchall()

    photos = [r["photo_id"] for r in photo_rows]
    if not photos and p["photo_id"]:
        photos = [p["photo_id"]]

    return JSONResponse({
        "id": p["id"], "name": p["name"], "category": p["category"],
        "description": p["description"] or "", "price": p["price"],
        "stock": p["stock"], "photos": photos,
    })


@router.get("/api/photo/{file_id:path}")
async def product_photo(file_id: str):
    bot_token = os.getenv("BOT_TOKEN", "")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        ) as resp:
            data = await resp.json()
        if not data.get("ok"):
            return JSONResponse({"error": "telegram error"}, status_code=404)
        file_path = data["result"]["file_path"]
        async with session.get(
            f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        ) as img_resp:
            content = await img_resp.read()
            content_type = img_resp.headers.get("Content-Type", "image/jpeg")
    return StreamingResponse(iter([content]), media_type=content_type)
