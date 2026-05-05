import os
import logging
import asyncpg
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"
)


def confirm_repeat_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"repeat_confirm_{order_id}")],
        [InlineKeyboardButton(text="❌ Скасувати",   callback_data="repeat_cancel")],
    ])


@router.message(F.text == "🔄 Повторити замовлення")
async def repeat_order(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Знайти останнє замовлення клієнта
        order = await conn.fetchrow("""
            SELECT o.id, o.total_price, o.address, o.phone
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            WHERE c.telegram_id = $1 AND o.status != 'cancelled'
            ORDER BY o.created_at DESC
            LIMIT 1
        """, message.from_user.id)

        if not order:
            await message.answer(
                "У тебе ще немає замовлень.\n"
                "Перегляни 🛍 Каталог щоб зробити перше!"
            )
            return

        # Отримати всі товари цього замовлення
        items = await conn.fetch("""
            SELECT p.name, oi.quantity, oi.price_at_order
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = $1
        """, order['id'])
    finally:
        await conn.close()

    items_text = "\n".join(
        f"• {i['name']} × {i['quantity']} шт — {i['price_at_order'] * i['quantity']} грн"
        for i in items
    )

    await message.answer(
        f"🔄 <b>Повторити останнє замовлення?</b>\n\n"
        f"{items_text}\n\n"
        f"💰 Сума: {order['total_price']} грн\n"
        f"📍 Адреса: {order['address']}\n"
        f"📞 Телефон: {order['phone']}",
        reply_markup=confirm_repeat_keyboard(order['id'])
    )


@router.callback_query(F.data.startswith("repeat_confirm_"))
async def confirm_repeat(callback: CallbackQuery):
    original_id = int(callback.data.replace("repeat_confirm_", ""))

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Отримати дані оригінального замовлення
        orig = await conn.fetchrow("""
            SELECT customer_id, address, phone, notes
            FROM orders WHERE id = $1
        """, original_id)

        if not orig:
            await callback.answer("Замовлення не знайдено", show_alert=True)
            return

        # Отримати всі позиції з поточними цінами і залишками
        items = await conn.fetch("""
            SELECT oi.product_id, oi.quantity, p.price as current_price,
                   p.stock, p.name, p.is_active
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = $1
        """, original_id)

        # Перевірити доступність всіх товарів
        for item in items:
            if not item['is_active']:
                await callback.answer(
                    f"На жаль, '{item['name']}' більше не доступний.",
                    show_alert=True
                )
                return
            if item['stock'] < item['quantity']:
                await callback.answer(
                    f"На жаль, '{item['name']}' зараз недостатньо в наявності "
                    f"(є {item['stock']} шт).",
                    show_alert=True
                )
                return

        total = sum(i['quantity'] * i['current_price'] for i in items)

        # Створити нове замовлення
        new_order_id = await conn.fetchval(
            "INSERT INTO orders (customer_id, address, phone, notes, total_price, status) VALUES ($1, $2, $3, $4, $5, 'new') RETURNING id",
            orig['customer_id'], orig['address'], orig['phone'], orig['notes'], total
        )

        for item in items:
            await conn.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price_at_order) VALUES ($1, $2, $3, $4)",
                new_order_id, item['product_id'], item['quantity'], item['current_price']
            )
            # Зменшити залишок
            await conn.execute(
                "UPDATE products SET stock = GREATEST(0, stock - $1) WHERE id = $2",
                item['quantity'], item['product_id']
            )

        await conn.execute(
            "UPDATE customers SET total_orders = total_orders + 1, last_order = CURRENT_TIMESTAMP WHERE id = $1",
            orig['customer_id']
        )
    finally:
        await conn.close()

    items_summary = "\n".join(
        f"• {i['name']} × {i['quantity']} — {i['quantity'] * i['current_price']} грн"
        for i in items
    )

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Замовлення #{new_order_id} створено!\n\n"
        f"{items_summary}\n\n"
        f"💰 Сума: {total} грн\n"
        "Ми зв'яжемось для підтвердження. Дякуємо! 🙏",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🚫 Скасувати замовлення",
                callback_data=f"cancel_order_{new_order_id}"
            )]
        ])
    )

    # Повідомити адміна
    admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    for admin_id in admin_ids:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🔄 <b>ПОВТОРНЕ ЗАМОВЛЕННЯ #{new_order_id}</b>\n\n"
                f"{items_summary}\n"
                f"💰 Сума: {total} грн\n"
                f"📍 Адреса: {orig['address']}\n"
                f"📞 Телефон: {orig['phone']}\n"
                f"Клієнт: @{callback.from_user.username or '—'}"
            )
        except Exception as e:
            logger.error(f"Не вдалось надіслати адміну: {e}")

    await callback.answer()


@router.callback_query(F.data == "repeat_cancel")
async def cancel_repeat(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Скасовано.")
    await callback.answer()
