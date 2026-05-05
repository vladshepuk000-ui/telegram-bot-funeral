import os
import asyncpg
from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"
)


@router.callback_query(F.data.startswith("waitlist_"))
async def add_to_waitlist(callback: CallbackQuery):
    product_id = int(callback.data.replace("waitlist_", ""))

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Отримати customer_id
        customer = await conn.fetchrow(
            "SELECT id FROM customers WHERE telegram_id = $1", callback.from_user.id
        )

        if not customer:
            await callback.answer("Спочатку напиши /start", show_alert=True)
            return

        # Перевірити чи вже в списку
        existing = await conn.fetchrow(
            "SELECT id FROM waitlist WHERE customer_id = $1 AND product_id = $2",
            customer['id'], product_id
        )

        if existing:
            await callback.answer(
                "Ти вже в списку очікування на цей товар.",
                show_alert=True
            )
            return

        # Додати в waitlist
        await conn.execute(
            "INSERT INTO waitlist (customer_id, product_id) VALUES ($1, $2)",
            customer['id'], product_id
        )
    finally:
        await conn.close()

    await callback.answer(
        "Ми сповістимо тебе як тільки товар з'явиться!",
        show_alert=True
    )
