import sqlite3
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = "vape_shop.db"
DATABASE_URL = "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"


async def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cur = sqlite_conn.cursor()

    pg = await asyncpg.connect(DATABASE_URL)

    # --- products ---
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    print(f"Товарів в SQLite: {len(products)}")
    for p in products:
        try:
            await pg.execute("""
                INSERT INTO products (id, name, category, description, price, stock, photo_id, photo_url, is_active)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO NOTHING
            """, p["id"], p["name"], p["category"], p["description"],
                float(p["price"]), int(p["stock"]),
                p["photo_id"] if "photo_id" in p.keys() else None,
                p["photo_url"] if "photo_url" in p.keys() else None,
                bool(p["is_active"]) if "is_active" in p.keys() else True)
            print(f"  + {p['name']}")
        except Exception as e:
            print(f"  ! Помилка {p['name']}: {e}")

    # Скинути sequence щоб нові товари не конфліктували
    await pg.execute("SELECT setval('products_id_seq', (SELECT MAX(id) FROM products))")

    # --- customers ---
    cur.execute("SELECT * FROM customers")
    customers = cur.fetchall()
    print(f"\nКлієнтів в SQLite: {len(customers)}")
    for c in customers:
        try:
            await pg.execute("""
                INSERT INTO customers (id, telegram_id, username, phone, is_subscribed, total_orders)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (id) DO NOTHING
            """, c["id"], int(c["telegram_id"]), c["username"], c["phone"],
                bool(c["is_subscribed"]) if "is_subscribed" in c.keys() else True,
                int(c["total_orders"]) if "total_orders" in c.keys() else 0)
        except Exception as e:
            print(f"  ! Помилка customer {c['id']}: {e}")

    if customers:
        await pg.execute("SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers))")
    print(f"  Перенесено {len(customers)} клієнтів")

    sqlite_conn.close()
    await pg.close()
    print("\nМіграція завершена!")


if __name__ == "__main__":
    asyncio.run(migrate())
