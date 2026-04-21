import os
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


class EditProduct(StatesGroup):
    choosing_product = State()
    choosing_field   = State()
    entering_value   = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def fields_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Назва",    callback_data=f"edit_name_{product_id}")],
        [InlineKeyboardButton(text="📄 Опис",     callback_data=f"edit_description_{product_id}")],
        [InlineKeyboardButton(text="💰 Ціна",     callback_data=f"edit_price_{product_id}")],
        [InlineKeyboardButton(text="📦 Залишок",  callback_data=f"edit_stock_{product_id}")],
        [InlineKeyboardButton(text="🖼 Фото",     callback_data=f"edit_photo_{product_id}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="edit_cancel")],
    ])


@router.message(Command("editproduct"))
async def cmd_editproduct(message: Message, state: FSMContext):
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
            callback_data=f"editprod_{p['id']}"
        )]
        for p in products
    ]
    await state.set_state(EditProduct.choosing_product)
    await message.answer(
        "Який товар хочеш змінити?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("editprod_"))
async def choose_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.replace("editprod_", ""))
    await state.update_data(product_id=product_id)
    await state.set_state(EditProduct.choosing_field)

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ) as cursor:
            p = await cursor.fetchone()

    await callback.message.edit_text(
        f"Товар: <b>{p['name']}</b>\n"
        f"Опис: {p['description']}\n"
        f"Ціна: {p['price']} грн\n"
        f"Залишок: {p['stock']} шт\n\n"
        "Що хочеш змінити?",
        reply_markup=fields_keyboard(product_id)
    )
    await callback.answer()


ALLOWED_FIELDS = {"name", "description", "price", "stock", "photo"}


@router.callback_query(F.data.startswith("edit_") & ~F.data.startswith("editprod_"))
async def choose_field(callback: CallbackQuery, state: FSMContext):
    if callback.data == "edit_cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Скасовано.")
        await callback.answer()
        return

    # edit_name_3, edit_description_3, edit_price_3 тощо
    # розбиваємо з maxsplit=2 щоб обробити довгі назви полів коректно
    try:
        _, field, product_id_str = callback.data.split("_", 2)
        product_id = int(product_id_str)
    except (ValueError, IndexError):
        await callback.answer("Невірний запит.", show_alert=True)
        return

    if field not in ALLOWED_FIELDS:
        await callback.answer("Невірне поле.", show_alert=True)
        return

    await state.update_data(field=field, product_id=product_id)
    await state.set_state(EditProduct.entering_value)

    field_names = {
        "name":        "нову назву",
        "description": "новий опис",
        "price":       "нову ціну (число)",
        "stock":       "нову кількість (число)",
        "photo":       "нове фото (надішли зображення)",
    }

    await callback.message.answer(f"Введи {field_names.get(field, field)}:")
    await callback.answer()


@router.message(EditProduct.entering_value, F.photo)
async def save_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE products SET photo_id = ? WHERE id = ?",
            (photo_id, data['product_id'])
        )
        await db.commit()

    await state.clear()
    await message.answer("✅ Фото оновлено!")


@router.message(EditProduct.entering_value)
async def save_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    product_id = data['product_id']
    value = message.text.strip()

    # Валідація числових полів
    if field in ("price", "stock"):
        try:
            value = float(value) if field == "price" else int(value)
        except ValueError:
            await message.answer("Введи числове значення, наприклад: 120")
            return

    # field перевірено вище через ALLOWED_FIELDS — безпечно для підстановки в SQL
    column = field  # вже провалідовано
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            f"UPDATE products SET {column} = ? WHERE id = ?",
            (value, product_id)
        )
        await db.commit()

    await state.clear()

    field_names = {
        "name":        "Назва",
        "description": "Опис",
        "price":       "Ціна",
        "stock":       "Залишок",
    }
    await message.answer(f"✅ {field_names.get(field, field)} оновлено!")
