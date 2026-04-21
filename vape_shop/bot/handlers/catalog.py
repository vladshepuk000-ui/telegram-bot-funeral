from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database.queries import get_all_products, get_products_by_category, get_product_by_id

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
        [InlineKeyboardButton(text=f"{p['name']} — {p['price']} грн", callback_data=f"product_{p['id']}")]
        for p in products
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cat_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_keyboard(product_id: int, in_stock: bool = True) -> InlineKeyboardMarkup:
    if in_stock:
        buttons = [
            [InlineKeyboardButton(text="🛒 Замовити", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="cat_back")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="🔔 Сповісти коли з'явиться", callback_data=f"waitlist_{product_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="cat_back")],
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

    await callback.message.edit_text(
        f"📦 {title}:",
        reply_markup=products_keyboard(products, category)
    )
    await callback.answer()


# ── Картка товару ──
@router.callback_query(F.data.startswith("product_"))
async def show_product(callback):
    product_id = int(callback.data.replace("product_", ""))
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
    if product['photo_id']:
        await callback.message.answer_photo(
            photo=product['photo_id'],
            caption=text,
            reply_markup=product_keyboard(product_id, in_stock)
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=product_keyboard(product_id, in_stock)
        )

    await callback.answer()
