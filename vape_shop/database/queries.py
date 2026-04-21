import aiosqlite
import os
from dotenv import load_dotenv

load_dotenv()

_db_url = os.getenv("DATABASE_URL", "vape_shop.db")
DATABASE_URL = _db_url.replace("sqlite:///", "")


# ─────────────────────────────────────────
# КЛІЄНТИ
# ─────────────────────────────────────────

async def add_customer(telegram_id: int, username: str = None) -> None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("""
            INSERT INTO customers (telegram_id, username)
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET username = excluded.username
        """, (telegram_id, username))
        await db.commit()


async def get_customer(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM customers WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_subscribed_customers() -> list[dict]:
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM customers WHERE is_subscribed = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def set_subscribed(telegram_id: int, value: bool) -> None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE customers SET is_subscribed = ? WHERE telegram_id = ?",
            (1 if value else 0, telegram_id)
        )
        await db.commit()


# ─────────────────────────────────────────
# ТОВАРИ
# ─────────────────────────────────────────

async def get_all_products(only_active: bool = True) -> list[dict]:
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM products"
        if only_active:
            query += " WHERE is_active = 1"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_products_by_category(category: str) -> list[dict]:
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM products WHERE category = ? AND is_active = 1", (category,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_product_by_id(product_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_stock(product_id: int, new_stock: int) -> None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id)
        )
        await db.commit()


# ─────────────────────────────────────────
# РОЗСИЛКИ
# ─────────────────────────────────────────

async def get_next_broadcast_template() -> dict | None:
    """Повертає шаблон який найдавніше використовувався"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM broadcast_templates
            ORDER BY last_used ASC NULLS FIRST
            LIMIT 1
        """) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def mark_template_used(template_id: int) -> None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("""
            UPDATE broadcast_templates
            SET used_count = used_count + 1,
                last_used = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (template_id,))
        await db.commit()


async def log_broadcast(text: str, sent: int, errors: int) -> None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "INSERT INTO broadcasts (text, sent_count, error_count) VALUES (?, ?, ?)",
            (text, sent, errors)
        )
        await db.commit()


async def add_broadcast_template(text: str) -> None:
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "INSERT INTO broadcast_templates (text) VALUES (?)", (text,)
        )
        await db.commit()


async def get_waitlist_for_product(product_id: int) -> list[dict]:
    """Повертає список telegram_id клієнтів що чекають на товар"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT c.telegram_id, w.id as waitlist_id
            FROM waitlist w
            JOIN customers c ON w.customer_id = c.id
            WHERE w.product_id = ?
        """, (product_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def clear_waitlist_for_product(product_id: int) -> None:
    """Видаляє всіх з waitlist після сповіщення"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "DELETE FROM waitlist WHERE product_id = ?", (product_id,)
        )
        await db.commit()
