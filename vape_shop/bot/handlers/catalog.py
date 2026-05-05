import os
import asyncpg
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from database.queries import get_all_products, get_products_by_category, get_product_by_id

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"
)

router = Router()

CATEGORIES = {
    "liquids":     "Рідини",
    "cartridges":  "Картриджі",
    "systems":     "Системи (поди)",
}


def categories_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"cat_{key}")]
        for key, name in CATEGORIES.items()
    ]
    buttons.append([InlineKeyboardButton(text="Всі товари", callback_data="cat_all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def products_keyboard(products: list, category: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{p['name']} — {p['price']} грн", callback_data=f"product_{p['id']}_{category}")]
        for p in products
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cat_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_keyboard(product_id: int, category: str, in_stock: bool = True) -> InlineKeyboardMarkup:
    if in_stock:
        buttons = [
            [InlineKeyboardButton(text="🛒 Замовити", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_{category}")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="🔔 Сповісти коли з'явиться", callback_data=f"waitlist_{product_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_{category}")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Кнопка "Каталог" з головного меню ──
@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: Message):
    await message.answer(
        "Оберіть категорію:",
        reply_markup=categories_keyboard()
    )


# ── Вибір категорії ──
@router.callback_query(F.data.startswith("cat_"))
async def show_category(callback):
    category = callback.data.replace("cat_", "")

    if category == "back":
        try:
            await callback.message.edit_text(
                "Оберіть категорію:",
                reply_markup=categories_keyboard()
            )
        except Exception:
            await callback.message.answer(
                "Оберіть категорію:",
                reply_markup=categories_keyboard()
            )
        await callback.answer()
        return

    if category == "all":
        products = await get_all_products()
        title = "Всі товари"
    else:
        products = await get_products_by_category(category)
        title = CATEGORIES.get(category, category)

    if not products:
        await callback.answer("Товарів в цій категорії немає", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            f"📦 {title}:",
            reply_markup=products_keyboard(products, category)
        )
    except Exception:
        await callback.message.answer(
            f"📦 {title}:",
            reply_markup=products_keyboard(products, category)
        )
    await callback.answer()


# ── Картка товару ──
@router.callback_query(F.data.startswith("product_"))
async def show_product(callback):
    parts = callback.data.replace("product_", "").split("_", 1)
    product_id = int(parts[0])
    category = parts[1] if len(parts) > 1 else "back"
    product = await get_product_by_id(product_id)

    if not product:
        await callback.answer("Товар не знайдено", show_alert=True)
        return

    stock_text = f"✅ В наявності: {product['stock']} шт" if product['stock'] > 0 else "❌ Немає в наявності"

    text = (
        f"<b>{product['name']}</b>\n\n"
        f"{product['description'] or ''}\n\n"
        f"💰 Ціна: {product['price']} грн\n"
        f"{stock_text}"
    )

    in_stock = product['stock'] > 0
    kb = product_keyboard(product_id, category, in_stock)

    # Отримати всі фото товару
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT photo_id FROM product_photos WHERE product_id = $1 ORDER BY position",
            product_id
        )
    finally:
        await conn.close()
    photos = [r["photo_id"] for r in rows]

    # Якщо в product_photos немає — використати старе photo_id
    if not photos and product['photo_id']:
        photos = [product['photo_id']]

    if len(photos) > 1:
        media = [InputMediaPhoto(media=p) for p in photos]
        await callback.message.answer_media_group(media)
        await callback.message.answer(text, reply_markup=kb)
    elif len(photos) == 1:
        await callback.message.answer_photo(photos[0], caption=text, reply_markup=kb)
    else:
        await callback.message.answer(text, reply_markup=kb)

    await callback.answer()
