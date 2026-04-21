from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from database.queries import add_customer, set_subscribed

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
async def cmd_start(message: Message):
    await add_customer(
        telegram_id=message.from_user.id,
        username=message.from_user.username
    )
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
