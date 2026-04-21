import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

FAQ = {
    "delivery": {
        "question": "🚚 Як відбувається доставка?",
        "answer": "Відправляємо Новою Поштою. Після підтвердження замовлення пакуємо і відправляємо протягом 1-2 днів."
    },
    "delivery_cost": {
        "question": "💸 Скільки коштує доставка?",
        "answer": "Доставка від 80 грн за тарифами Нової Пошти."
    },
    "payment": {
        "question": "💳 Як відбувається оплата?",
        "answer": "Повна оплата на картку або накладений платіж."
    },
    "availability": {
        "question": "📦 Як дізнатись що є в наявності?",
        "answer": "Актуальний асортимент завжди в розділі 🛍 Каталог — там тільки те що є в наявності."
    },
    "cancel": {
        "question": "❌ Як скасувати замовлення?",
        "answer": "Напишіть нам до відправки — скасуємо без проблем."
    },
    "minimum": {
        "question": "📏 Мінімальне замовлення?",
        "answer": "Без обмежень — можна замовити 1 одиницю."
    },
    "cities": {
        "question": "🗺 В які міста доставляєте?",
        "answer": "По всій Україні через Нову Пошту."
    },
}


def faq_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=v["question"], callback_data=f"faq_{k}")]
        for k, v in FAQ.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад до питань", callback_data="faq_back")]
    ])


def payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Повна оплата на картку", callback_data="pay_card")],
        [InlineKeyboardButton(text="📦 Накладений платіж", callback_data="pay_cod")],
        [InlineKeyboardButton(text="⬅️ Назад до питань", callback_data="faq_back")],
    ])


@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message):
    await message.answer(
        "Часті запитання — обери що тебе цікавить:",
        reply_markup=faq_keyboard()
    )


@router.callback_query(F.data == "faq_back")
async def faq_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "Часті запитання — обери що тебе цікавить:",
        reply_markup=faq_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "pay_card")
async def payment_card(callback: CallbackQuery):
    card = os.getenv("PAYMENT_CARD", "номер не вказано")
    name = os.getenv("PAYMENT_NAME", "")
    await callback.message.edit_text(
        f"💳 <b>Оплата на картку:</b>\n\n"
        f"Номер картки: <code>{card}</code>\n"
        f"Отримувач: {name}\n\n"
        f"Після оплати надішліть скріншот підтвердження.",
        reply_markup=back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "pay_cod")
async def payment_cod(callback: CallbackQuery):
    await callback.message.edit_text(
        "📦 <b>Накладений платіж:</b>\n\n"
        "Оплата при отриманні на відділенні Нової Пошти.\n"
        "Комісія НП — 2% від суми замовлення + 20 грн.",
        reply_markup=back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq_"))
async def show_answer(callback: CallbackQuery):
    key = callback.data.replace("faq_", "")
    item = FAQ.get(key)

    if not item:
        await callback.answer("Питання не знайдено", show_alert=True)
        return

    # Для оплати — показуємо кнопки вибору
    if key == "payment":
        await callback.message.edit_text(
            f"<b>{item['question']}</b>\n\nОбери спосіб оплати:",
            reply_markup=payment_keyboard()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"<b>{item['question']}</b>\n\n{item['answer']}",
        reply_markup=back_keyboard()
    )
    await callback.answer()
