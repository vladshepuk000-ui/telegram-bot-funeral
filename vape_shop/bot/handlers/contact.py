from aiogram import Router, F
from aiogram.types import Message
import os

router = Router()


@router.message(F.text == "📞 Контакт")
async def show_contact(message: Message):
    username = os.getenv("CONTACT_USERNAME", "не вказано")
    phone = os.getenv("CONTACT_PHONE", "не вказано")

    lines = ["📞 <b>Зв'язок з продавцем:</b>\n"]
    if username != "не вказано":
        lines.append(f"Telegram: @{username}")
    if phone != "не вказано":
        lines.append(f"Телефон: {phone}")
    lines.append("\nПишіть — відповімо якнайшвидше 👋")

    await message.answer("\n".join(lines))
