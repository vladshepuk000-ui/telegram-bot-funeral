import os
import logging
import asyncpg
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway"
)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class BroadcastForm(StatesGroup):
    entering_text = State()
    confirming    = State()


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Надіслати всім", callback_data="bc_confirm")],
        [InlineKeyboardButton(text="💾 Зберегти як шаблон і надіслати", callback_data="bc_save_send")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="bc_cancel")],
    ])


# ── /broadcast — почати розсилку ──
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(BroadcastForm.entering_text)
    await message.answer(
        "✍️ Введи текст розсилки:\n\n"
        "<i>Підтримується HTML: <b>жирний</b>, <i>курсив</i>, <code>код</code></i>\n\n"
        "Або /cancel щоб скасувати."
    )


@router.message(BroadcastForm.entering_text)
async def enter_broadcast_text(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Введи текст повідомлення.")
        return

    await state.update_data(text=message.text)
    await state.set_state(BroadcastForm.confirming)

    # Показати превью
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM customers WHERE is_subscribed = TRUE"
        )
    finally:
        await conn.close()

    await message.answer(
        f"📋 <b>Превью розсилки:</b>\n\n"
        f"{message.text}\n\n"
        f"─────────────────\n"
        f"Отримувачів: <b>{total}</b> клієнтів\n\n"
        "Надсилаємо?",
        reply_markup=broadcast_confirm_keyboard()
    )


@router.callback_query(F.data.in_({"bc_confirm", "bc_save_send"}))
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data['text']
    save_template = callback.data == "bc_save_send"
    await state.clear()

    await callback.message.edit_reply_markup(reply_markup=None)
    status_msg = await callback.message.answer("⏳ Надсилаю...")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if save_template:
            await conn.execute(
                "INSERT INTO broadcast_templates (text) VALUES ($1)", text
            )

        customers = await conn.fetch(
            "SELECT telegram_id FROM customers WHERE is_subscribed = TRUE"
        )

        sent = 0
        errors = 0
        for c in customers:
            try:
                await callback.bot.send_message(c['telegram_id'], text)
                sent += 1
            except Exception:
                errors += 1

        await conn.execute(
            "INSERT INTO broadcasts (text, sent_count, error_count) VALUES ($1, $2, $3)",
            text, sent, errors
        )
    finally:
        await conn.close()

    await status_msg.edit_text(
        f"✅ Розсилку завершено!\n\n"
        f"Надіслано: {sent}\n"
        f"Помилок: {errors}"
        + ("\n💾 Збережено як шаблон" if save_template else "")
    )
    await callback.answer()


@router.callback_query(F.data == "bc_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Розсилку скасовано.")
    await callback.answer()


# ── /addtemplate — додати шаблон авторозсилки ──
@router.message(Command("addtemplate"))
async def cmd_addtemplate(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # Текст після команди
    text = message.text.replace("/addtemplate", "").strip()
    if not text:
        await message.answer(
            "Формат: /addtemplate [текст шаблону]\n\n"
            "Приклад:\n/addtemplate 🔥 Нові надходження! Заходь до каталогу 👉 /start"
        )
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "INSERT INTO broadcast_templates (text) VALUES ($1)", text
        )
    finally:
        await conn.close()

    await message.answer("✅ Шаблон збережено! Він буде використаний в авторозсилці.")


# ── /templates — переглянути шаблони ──
@router.message(Command("templates"))
async def cmd_templates(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        templates = await conn.fetch(
            "SELECT * FROM broadcast_templates ORDER BY last_used ASC NULLS FIRST"
        )
    finally:
        await conn.close()

    if not templates:
        await message.answer(
            "Шаблонів немає.\n"
            "Додай через /addtemplate [текст]"
        )
        return

    text = "📋 <b>Шаблони авторозсилки:</b>\n\n"
    for t in templates:
        used = str(t['last_used'])[:10] if t['last_used'] else "ніколи"
        text += (
            f"#{t['id']} (використано: {t['used_count']}р, останній раз: {used})\n"
            f"{t['text'][:80]}{'...' if len(t['text']) > 80 else ''}\n\n"
        )

    await message.answer(text)
