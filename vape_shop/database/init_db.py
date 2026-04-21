import aiosqlite
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

_db_url = os.getenv("DATABASE_URL", "vape_shop.db")
DATABASE_URL = _db_url.replace("sqlite:///", "")


async def create_tables():
    async with aiosqlite.connect(DATABASE_URL) as db:

        # Товари
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                category    TEXT NOT NULL,
                description TEXT,
                price       REAL NOT NULL,
                stock       INTEGER DEFAULT 0,
                photo_id    TEXT,
                photo_url   TEXT,
                is_active   BOOLEAN DEFAULT 1,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Клієнти
        await db.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id   INTEGER UNIQUE NOT NULL,
                username      TEXT,
                phone         TEXT,
                is_subscribed BOOLEAN DEFAULT 1,
                first_seen    DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_order    DATETIME,
                total_orders  INTEGER DEFAULT 0
            )
        """)

        # Замовлення
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                address     TEXT,
                phone       TEXT,
                notes       TEXT,
                total_price REAL,
                status      TEXT DEFAULT 'new',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Позиції замовлення
        await db.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id       INTEGER REFERENCES orders(id),
                product_id     INTEGER REFERENCES products(id),
                quantity       INTEGER NOT NULL,
                price_at_order REAL NOT NULL
            )
        """)

        # Список очікування товару
        await db.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                product_id  INTEGER REFERENCES products(id),
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Відгуки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                order_id    INTEGER REFERENCES orders(id),
                rating      INTEGER NOT NULL,
                text        TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Шаблони авторозсилок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_templates (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT NOT NULL,
                used_count INTEGER DEFAULT 0,
                last_used  DATETIME
            )
        """)

        # Логування розсилок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                text        TEXT NOT NULL,
                sent_count  INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Контекст AI розмов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_chat_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Лічильник AI запитів
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_usage (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                date        DATE NOT NULL,
                count       INTEGER DEFAULT 0
            )
        """)

        await db.commit()
        print("OK: Всі таблиці створено успішно")


if __name__ == "__main__":
    asyncio.run(create_tables())
