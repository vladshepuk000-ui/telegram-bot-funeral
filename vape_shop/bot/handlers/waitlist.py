import os
import aiosqlite
from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")


@router.callback_query(F.data.startswith("waitlist_"))
async def add_to_waitlist(callback: CallbackQuery):
    product_id = int(callback.data.replace("waitlist_", ""))

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        # Отримати customer_id
        async with db.execute(
            "SELECT id FROM customers WHERE telegram_id = ?", (callback.from_user.id,)
        ) as cursor:
            customer = await cursor.fetchone()

        if not customer:
            await callback.answer("Спочатку напиши /start", show_alert=True)
            return

        # Перевірити чи вже в списку
        async with db.execute(
            "SELECT id FROM waitlist WHERE customer_id = ? AND product_id = ?",
            (customer['id'], product_id)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            await callback.answer(
                "Ти вже в списку очікування на цей товар.",
                show_alert=True
            )
            return

        # Додати в waitlist
        await db.execute(
            "INSERT INTO waitlist (customer_id, product_id) VALUES (?, ?)",
            (customer['id'], product_id)
        )
        await db.commit()

    await callback.answer(
        "Ми сповістимо тебе як тільки товар з'явиться!",
        show_alert=True
    )
