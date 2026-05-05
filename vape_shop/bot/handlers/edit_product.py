import os
import asyncpg
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"
)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


class EditProduct(StatesGroup):
    choosing_product = State()
    choosing_field   = State()
    entering_value   = State()
    managing_photos  = State()


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


def edit_photos_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати ще фото", callback_data="editphoto_more")],
        [InlineKeyboardButton(text="✅ Готово",          callback_data="editphoto_done")],
    ])


@router.message(Command("editproduct"))
async def cmd_editproduct(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        products = await conn.fetch(
            "SELECT id, name, price FROM products WHERE is_active = TRUE"
        )
    finally:
        await conn.close()

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

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        p = await conn.fetchrow(
            "SELECT * FROM products WHERE id = $1", product_id
        )
        photo_count = await conn.fetchval(
            "SELECT COUNT(*) FROM product_photos WHERE product_id = $1", product_id
        )
    finally:
        await conn.close()

    if photo_count == 0 and p['photo_id']:
        photo_count = 1

    await callback.message.edit_text(
        f"Товар: <b>{p['name']}</b>\n"
        f"Опис: {p['description']}\n"
        f"Ціна: {p['price']} грн\n"
        f"Залишок: {p['stock']} шт\n"
        f"Фото: {photo_count} шт\n\n"
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

    try:
        _, field, product_id_str = callback.data.split("_", 2)
        product_id = int(product_id_str)
    except (ValueError, IndexError):
        await callback.answer("Невірний запит.", show_alert=True)
        return

    if field not in ALLOWED_FIELDS:
        await callback.answer("Невірне поле.", show_alert=True)
        return

    await state.update_data(field=field, product_id=product_id, new_photos=[])

    if field == "photo":
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM product_photos WHERE product_id = $1", product_id
            )
        finally:
            await conn.close()

        await state.set_state(EditProduct.managing_photos)
        await callback.message.answer(
            f"Зараз фото: <b>{cnt} шт</b>\n\n"
            "Надішли нові фото по черзі. Вони <b>замінять</b> всі поточні.\n"
            "Після останнього фото натисни ✅ Готово."
        )
    else:
        await state.set_state(EditProduct.entering_value)
        field_names = {
            "name":        "нову назву",
            "description": "новий опис",
            "price":       "нову ціну (число)",
            "stock":       "нову кількість (число)",
        }
        await callback.message.answer(f"Введи {field_names.get(field, field)}:")

    await callback.answer()


# ── Отримати нове фото при редагуванні ──
@router.message(EditProduct.managing_photos, ~F.photo)
async def edit_photo_wrong_type(message: Message):
    await message.answer("Надішли фото або натисни ✅ Готово.")


@router.message(EditProduct.managing_photos, F.photo)
async def edit_add_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    new_photos = data.get('new_photos', [])

    if len(new_photos) >= 10:
        await message.answer("Максимум 10 фото. Натисни ✅ Готово.")
        return

    new_photos.append(message.photo[-1].file_id)
    await state.update_data(new_photos=new_photos)
    await message.answer(
        f"Фото {len(new_photos)} додано ✅",
        reply_markup=edit_photos_keyboard()
    )


@router.callback_query(F.data == "editphoto_more")
async def editphoto_more(callback: CallbackQuery):
    await callback.message.answer("Надішли наступне фото:")
    await callback.answer()


@router.callback_query(F.data == "editphoto_done")
async def editphoto_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data['product_id']
    new_photos = data.get('new_photos', [])

    if not new_photos:
        await callback.answer("Ти не додав жодного фото.", show_alert=True)
        return

    main_photo = new_photos[0]

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Видалити старі фото
        await conn.execute("DELETE FROM product_photos WHERE product_id = $1", product_id)
        # Оновити головне фото
        await conn.execute("UPDATE products SET photo_id = $1 WHERE id = $2", main_photo, product_id)
        # Зберегти нові
        for i, pid in enumerate(new_photos):
            await conn.execute(
                "INSERT INTO product_photos (product_id, photo_id, position) VALUES ($1, $2, $3)",
                product_id, pid, i
            )
    finally:
        await conn.close()

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✅ Фото оновлено! Додано {len(new_photos)} шт.")
    await callback.answer()


# ── Зберегти текстове значення ──
@router.message(EditProduct.entering_value, F.photo)
async def save_photo_legacy(message: Message, state: FSMContext):
    """Якщо надіслали фото не в режимі managing_photos — ігноруємо."""
    await message.answer("Для зміни фото обери '🖼 Фото' в меню редагування.")


@router.message(EditProduct.entering_value)
async def save_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    product_id = data['product_id']
    value = message.text.strip()

    if field in ("price", "stock"):
        try:
            value = float(value) if field == "price" else int(value)
        except ValueError:
            await message.answer("Введи числове значення, наприклад: 120")
            return

    column = field  # вже провалідовано через ALLOWED_FIELDS
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            f"UPDATE products SET {column} = $1 WHERE id = $2",
            value, product_id
        )
    finally:
        await conn.close()

    await state.clear()

    field_names = {
        "name":        "Назва",
        "description": "Опис",
        "price":       "Ціна",
        "stock":       "Залишок",
    }
    await message.answer(f"✅ {field_names.get(field, field)} оновлено!")
