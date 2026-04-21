import os
import logging
import aiosqlite
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class ReviewForm(StatesGroup):
    entering_text = State()


def rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=stars[i], callback_data=f"rev_rate_{order_id}_{i+1}")]
        for i in range(5)
    ] + [
        [InlineKeyboardButton(text="Пропустити", callback_data=f"rev_skip_{order_id}")]
    ])


def add_comment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написати коментар", callback_data=f"rev_text_yes_{order_id}")],
        [InlineKeyboardButton(text="Ні, дякую", callback_data=f"rev_text_no_{order_id}")],
    ])


def send_review_request(order_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🙏 Дякуємо за замовлення!\n\n"
        "Будь ласка, оціни своє замовлення — це допоможе нам стати кращими:"
    )
    return text, rating_keyboard(order_id)


# ── Клієнт обрав оцінку ──
@router.callback_query(F.data.startswith("rev_rate_"))
async def handle_rating(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    # rev_rate_{order_id}_{rating}
    order_id = int(parts[2])
    rating = int(parts[3])

    await state.update_data(order_id=order_id, rating=rating)

    stars = "⭐" * rating
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"Дякуємо! Ти поставив {stars}\n\n"
        "Хочеш додати коментар?",
        reply_markup=add_comment_keyboard(order_id)
    )
    await callback.answer()


# ── Пропустити оцінку ──
@router.callback_query(F.data.startswith("rev_skip_"))
async def handle_skip_rating(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Добре, дякуємо! Чекаємо тебе знову 😊")
    await callback.answer()


# ── Клієнт хоче написати коментар ──
@router.callback_query(F.data.startswith("rev_text_yes_"))
async def handle_want_comment(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[3])
    await state.update_data(order_id=order_id)
    await state.set_state(ReviewForm.entering_text)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Напиши свій відгук:")
    await callback.answer()


# ── Клієнт відмовився від коментаря ──
@router.callback_query(F.data.startswith("rev_text_no_"))
async def handle_no_comment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rating = data.get("rating", 0)
    order_id = int(callback.data.split("_")[3])

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)

    await _save_review(callback.bot, callback.from_user.id, order_id, rating, text=None)
    await callback.message.answer("Дякуємо за оцінку! 😊")
    await callback.answer()


# ── Клієнт вводить текст відгуку ──
@router.message(ReviewForm.entering_text)
async def handle_review_text(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Напиши текстовий відгук.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    rating = data.get("rating", 0)
    await state.clear()

    await _save_review(message.bot, message.from_user.id, order_id, rating, text=message.text)
    await message.answer("Дякуємо за відгук! Це дуже важливо для нас 🙏")


async def _save_review(bot, telegram_id: int, order_id: int, rating: int, text: str | None):
    """Зберегти відгук і сповістити адміна."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        # Знайти customer_id
        async with db.execute(
            "SELECT id, username FROM customers WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            customer = await cursor.fetchone()

        if not customer:
            return

        await db.execute(
            "INSERT INTO reviews (customer_id, order_id, rating, text) VALUES (?, ?, ?, ?)",
            (customer['id'], order_id, rating, text)
        )
        await db.commit()

    # Сповістити адміна
    stars = "⭐" * rating + "☆" * (5 - rating)
    username = f"@{customer['username']}" if customer['username'] else f"id:{telegram_id}"
    admin_text = (
        f"⭐ <b>Новий відгук</b> на замовлення #{order_id}\n\n"
        f"Клієнт: {username}\n"
        f"Оцінка: {stars} ({rating}/5)\n"
    )
    if text:
        admin_text += f"Коментар: {text}"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception as e:
            logger.error(f"Не вдалось сповістити адміна: {e}")


# ── /reviews — переглянути відгуки ──
@router.message(Command("reviews"))
async def cmd_reviews(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.rating, r.text, r.created_at,
                   c.username, c.telegram_id,
                   r.order_id
            FROM reviews r
            LEFT JOIN customers c ON r.customer_id = c.id
            ORDER BY r.created_at DESC
            LIMIT 20
        """) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("Відгуків ще немає.")
        return

    # Середня оцінка
    async with aiosqlite.connect(DATABASE_URL) as db:
        async with db.execute("SELECT AVG(rating) as avg, COUNT(*) as cnt FROM reviews") as cursor:
            stats = await cursor.fetchone()

    avg = round(stats[0], 1) if stats[0] else 0
    cnt = stats[1]

    text = f"⭐ <b>Відгуки клієнтів</b>\n"
    text += f"Середня оцінка: {avg}/5 ({cnt} відгуків)\n\n"

    for r in rows:
        stars = "⭐" * r['rating'] + "☆" * (5 - r['rating'])
        username = f"@{r['username']}" if r['username'] else f"id:{r['telegram_id']}"
        text += f"{stars} — #{r['order_id']} від {username}\n"
        if r['text']:
            preview = r['text'][:80] + ("..." if len(r['text']) > 80 else "")
            text += f"<i>{preview}</i>\n"
        text += f"<code>{r['created_at'][:10]}</code>\n\n"

    await message.answer(text)
