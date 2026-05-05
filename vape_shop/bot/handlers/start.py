from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.queries import add_customer, set_subscribed, get_product_by_id

router = Router()

# Головне меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог"),          KeyboardButton(text="📊 Мої замовлення")],
        [KeyboardButton(text="🔄 Повторити замовлення")],
        [KeyboardButton(text="❓ FAQ"),               KeyboardButton(text="📞 Контакт")],
    ],
    resize_keyboard=True
)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    await add_customer(
        telegram_id=message.from_user.id,
        username=message.from_user.username
    )

    # Deep link: /start product_123
    if command.args and command.args.startswith("product_"):
        try:
            product_id = int(command.args.replace("product_", ""))
            product = await get_product_by_id(product_id)
            if product:
                stock_text = f"✅ В наявності: {product['stock']} шт" if product['stock'] > 0 else "❌ Немає в наявності"
                text = (
                    f"<b>{product['name']}</b>\n\n"
                    f"{product['description'] or ''}\n\n"
                    f"💰 Ціна: {product['price']} грн\n"
                    f"{stock_text}"
                )
                if product['stock'] > 0:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🛒 Замовити", callback_data=f"buy_{product_id}")],
                        [InlineKeyboardButton(text="📦 Весь каталог", callback_data="cat_back")],
                    ])
                else:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔔 Сповісти коли з'явиться", callback_data=f"waitlist_{product_id}")],
                        [InlineKeyboardButton(text="📦 Весь каталог", callback_data="cat_back")],
                    ])
                await message.answer(
                    f"Привіт, {message.from_user.first_name}! 👋\n\nТи обрав товар з нашого сайту:",
                    reply_markup=main_menu
                )
                if product.get('photo_id'):
                    await message.answer_photo(product['photo_id'], caption=text, reply_markup=kb, parse_mode="HTML")
                else:
                    await message.answer(text, reply_markup=kb, parse_mode="HTML")
                return
        except (ValueError, Exception):
            pass

    await message.answer(
        f"Привіт, {message.from_user.first_name}! 👋\n\n"
        "Я бот вейп-магазину. Тут можна переглянути асортимент і зробити замовлення.\n\n"
        "Обирай що тебе цікавить 👇",
        reply_markup=main_menu
    )


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    await set_subscribed(message.from_user.id, False)
    await message.answer(
        "Ти відписався від розсилок. "
        "Щоб підписатись знову — напиши /start"
    )
