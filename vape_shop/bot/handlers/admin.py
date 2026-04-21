import os
import logging
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.queries import get_waitlist_for_product, clear_waitlist_for_product

router = Router()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

STATUS_MAP = {
    "awaiting_payment": "⏳ Очікує оплати",
    "new":              "🆕 Нове",
    "confirmed":        "✅ Підтверджено",
    "sent":             "🚚 Відправлено",
    "done":             "✔️ Виконано",
    "cancelled":        "❌ Скасовано",
}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── FSM для додавання товару ──
class AddProduct(StatesGroup):
    name        = State()
    category    = State()
    description = State()
    price       = State()
    stock       = State()
    photo       = State()


# ── /orders — список останніх замовлень ──
@router.message(Command("orders"))
async def cmd_orders(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT o.id, o.status, o.total_price, o.created_at,
                   c.telegram_id, c.username,
                   p.name as product_name, oi.quantity
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN products p ON oi.product_id = p.id
            ORDER BY o.created_at DESC
            LIMIT 10
        """) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("Замовлень ще немає.")
        return

    text = "📋 <b>Останні 10 замовлень:</b>\n\n"
    for r in rows:
        status = STATUS_MAP.get(r['status'], r['status'])
        username = f"@{r['username']}" if r['username'] else f"id:{r['telegram_id']}"
        text += (
            f"#{r['id']} | {status}\n"
            f"{r['product_name']} x{r['quantity']} — {r['total_price']} грн\n"
            f"Клієнт: {username}\n"
            f"Дата: {r['created_at'][:16]}\n\n"
        )

    await message.answer(text)


# ── /setstatus — змінити статус замовлення ──
@router.message(Command("setstatus"))
async def cmd_setstatus(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) != 3 or args[2] not in STATUS_MAP:
        statuses = " | ".join(STATUS_MAP.keys())
        await message.answer(
            f"Формат: /setstatus [id] [статус]\n"
            f"Статуси: {statuses}\n\n"
            f"Приклад: /setstatus 5 sent"
        )
        return

    order_id = args[1]
    new_status = args[2]

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        # Перевірити чи існує замовлення
        async with db.execute(
            "SELECT o.*, c.telegram_id FROM orders o LEFT JOIN customers c ON o.customer_id = c.id WHERE o.id = ?",
            (order_id,)
        ) as cursor:
            order = await cursor.fetchone()

        if not order:
            await message.answer(f"Замовлення #{order_id} не знайдено.")
            return

        # Оновити статус
        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id)
        )
        await db.commit()

    status_text = STATUS_MAP[new_status]
    await message.answer(f"✅ Замовлення #{order_id} → {status_text}")

    # Повідомити клієнта
    if order['telegram_id']:
        try:
            await message.bot.send_message(
                order['telegram_id'],
                f"📦 Статус вашого замовлення #{order_id} змінено:\n"
                f"{status_text}"
            )
        except Exception as e:
            logger.error(f"Не вдалось надіслати клієнту: {e}")


# ── /addproduct — додати товар ──
@router.message(Command("addproduct"))
async def cmd_addproduct(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AddProduct.name)
    await message.answer(
        "Додавання нового товару.\n\n"
        "Введи назву товару:\n"
        "(або /cancel щоб скасувати)"
    )


@router.message(AddProduct.name)
async def add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProduct.category)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Рідини",         callback_data="addcat_liquids")],
        [InlineKeyboardButton(text="Картриджі",      callback_data="addcat_cartridges")],
        [InlineKeyboardButton(text="Системи (поди)", callback_data="addcat_systems")],
    ])
    await message.answer("Обери категорію:", reply_markup=kb)


@router.callback_query(F.data.startswith("addcat_"))
async def add_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("addcat_", "")
    await state.update_data(category=category)
    await state.set_state(AddProduct.description)
    await callback.message.answer("Введи опис товару (смак, міцність тощо):")
    await callback.answer()


@router.message(AddProduct.description)
async def add_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddProduct.price)
    await message.answer("Введи ціну (тільки число, наприклад: 120):")


@router.message(AddProduct.price)
async def add_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введи числову ціну, наприклад: 120")
        return

    await state.update_data(price=price)
    await state.set_state(AddProduct.stock)
    await message.answer("Скільки одиниць в наявності?")


@router.message(AddProduct.stock)
async def add_stock(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи ціле число, наприклад: 10")
        return

    await state.update_data(stock=int(message.text))
    await state.set_state(AddProduct.photo)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустити фото", callback_data="addphoto_skip")]
    ])
    await message.answer("Надішли фото товару або пропусти:", reply_markup=kb)


@router.callback_query(F.data == "addphoto_skip")
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    await save_product(callback.message, state, photo_id=None)
    await callback.answer()


@router.message(AddProduct.photo, F.photo)
async def add_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_product(message, state, photo_id=photo_id)


async def save_product(message: Message, state: FSMContext, photo_id: str | None):
    data = await state.get_data()
    await state.clear()

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("""
            INSERT INTO products (name, category, description, price, stock, photo_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data['name'], data['category'], data['description'],
            data['price'], data['stock'], photo_id
        ))
        await db.commit()

    await message.answer(
        f"✅ Товар <b>{data['name']}</b> додано!\n"
        f"Ціна: {data['price']} грн | Залишок: {data['stock']} шт"
    )


# ── /restock — поповнити залишок і сповістити waitlist ──
@router.message(Command("restock"))
async def cmd_restock(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
        await message.answer(
            "Формат: /restock [id_товару] [кількість]\n"
            "Приклад: /restock 3 10"
        )
        return

    product_id = int(args[1])
    quantity = int(args[2])

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT name FROM products WHERE id = ?", (product_id,)
        ) as cursor:
            product = await cursor.fetchone()

        if not product:
            await message.answer(f"Товар #{product_id} не знайдено.")
            return

        await db.execute(
            "UPDATE products SET stock = stock + ? WHERE id = ?",
            (quantity, product_id)
        )
        await db.commit()

    await message.answer(
        f"✅ Залишок товару <b>{product['name']}</b> поповнено на {quantity} шт."
    )

    # Сповістити всіх з waitlist
    waitlist = await get_waitlist_for_product(product_id)
    if waitlist:
        sent = 0
        for entry in waitlist:
            try:
                await message.bot.send_message(
                    entry['telegram_id'],
                    f"🔔 Товар <b>{product['name']}</b> знову є в наявності!\n"
                    "Поспішай замовити 👉 /start"
                )
                sent += 1
            except Exception:
                pass
        await clear_waitlist_for_product(product_id)
        await message.answer(f"Сповіщено {sent} клієнтів з листа очікування.")


# ── /removeproduct — видалити товар ──
@router.message(Command("removeproduct"))
async def cmd_removeproduct(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, price FROM products WHERE is_active = 1"
        ) as cursor:
            products = await cursor.fetchall()

    if not products:
        await message.answer("Немає активних товарів.")
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{p['name']} — {p['price']} грн",
            callback_data=f"remove_{p['id']}"
        )]
        for p in products
    ]
    await message.answer(
        "Який товар видалити?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("remove_"))
async def confirm_remove(callback: CallbackQuery):
    product_id = int(callback.data.replace("remove_", ""))

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT name FROM products WHERE id = ?", (product_id,)
        ) as cursor:
            product = await cursor.fetchone()

        await db.execute(
            "UPDATE products SET is_active = 0 WHERE id = ?", (product_id,)
        )
        await db.commit()

    await callback.message.edit_text(
        f"✅ Товар <b>{product['name']}</b> прибрано з каталогу."
    )
    await callback.answer()
