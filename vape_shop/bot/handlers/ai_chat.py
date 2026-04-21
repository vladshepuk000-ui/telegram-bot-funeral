import os
import logging
from datetime import date
import aiosqlite
import aiohttp
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.state import default_state

router = Router()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "vape_shop.db").replace("sqlite:///", "")

SYSTEM_PROMPT = (
    "Ти — помічник вейп-шопу. Відповідай українською мовою, коротко і по суті. "
    "Допомагай клієнтам обирати рідини, картриджі та системи (поди). "
    "Якщо питають про каталог або ціни — пропонуй переглянути /start. "
    "Якщо питають про замовлення або статус — пропонуй написати продавцю @Vlad_shepuk. "
    "Не вигадуй конкретних цін чи назв товарів — посилайся на каталог. "
    "Будь дружнім і лаконічним."
)


async def get_daily_usage(db, customer_id: int) -> int:
    """Повертає кількість AI-запитів клієнта сьогодні."""
    today = date.today().isoformat()
    async with db.execute(
        "SELECT count FROM ai_usage WHERE customer_id = ? AND date = ?",
        (customer_id, today)
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row else 0


async def increment_daily_usage(db, customer_id: int):
    today = date.today().isoformat()
    async with db.execute(
        "SELECT id FROM ai_usage WHERE customer_id = ? AND date = ?",
        (customer_id, today)
    ) as cursor:
        row = await cursor.fetchone()

    if row:
        await db.execute(
            "UPDATE ai_usage SET count = count + 1 WHERE customer_id = ? AND date = ?",
            (customer_id, today)
        )
    else:
        await db.execute(
            "INSERT INTO ai_usage (customer_id, date, count) VALUES (?, ?, 1)",
            (customer_id, today)
        )


async def get_chat_history(db, customer_id: int) -> list[dict]:
    """Останні 10 повідомлень для контексту."""
    async with db.execute("""
        SELECT role, content FROM ai_chat_history
        WHERE customer_id = ?
        ORDER BY created_at DESC
        LIMIT 4
    """, (customer_id,)) as cursor:
        rows = await cursor.fetchall()
    # Повертаємо у правильному порядку (від старих до нових)
    return [{"role": r[0], "parts": [r[1]]} for r in reversed(rows)]


async def save_message(db, customer_id: int, role: str, content: str):
    await db.execute(
        "INSERT INTO ai_chat_history (customer_id, role, content) VALUES (?, ?, ?)",
        (customer_id, role, content)
    )


async def get_catalog_context() -> str:
    """Повертає реальний список товарів з БД для системного промпту."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT name, description, price, stock FROM products WHERE is_active = 1 ORDER BY category"
        ) as cursor:
            products = await cursor.fetchall()

    if not products:
        return "Каталог порожній."

    lines = ["Товари (тільки ці існують):"]
    for p in products:
        avail = "✓" if p['stock'] > 0 else "✗"
        lines.append(f"{avail} {p['name']} — {p['price']} грн")
    return "\n".join(lines)


# ── Обробник вільних повідомлень — тільки коли немає активного FSM ──
@router.message(StateFilter(default_state), F.text)
async def handle_ai_message(message: Message):
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "your_groq_api_key_here":
        return

    ai_daily_limit = int(os.getenv("AI_DAILY_LIMIT", "30"))
    user_text = message.text.strip()

    # Ігноруємо команди — вони оброблені іншими роутерами
    if user_text.startswith("/"):
        return

    async with aiosqlite.connect(DATABASE_URL) as db:
        # Знайти customer_id
        async with db.execute(
            "SELECT id FROM customers WHERE telegram_id = ?",
            (message.from_user.id,)
        ) as cursor:
            customer = await cursor.fetchone()

        if not customer:
            logger.warning(f"Клієнт {message.from_user.id} не знайдений в БД")
            await message.answer("Спочатку натисни /start")
            return

        customer_id = customer[0]

        # Перевірити ліміт
        usage = await get_daily_usage(db, customer_id)
        if usage >= ai_daily_limit:
            await message.answer(
                f"⚠️ Ти вичерпав ліміт AI-запитів на сьогодні ({ai_daily_limit}).\n"
                "Спробуй завтра або напиши продавцю: @Vlad_shepuk"
            )
            return

        # Отримати історію розмови
        history = await get_chat_history(db, customer_id)

        # Зберегти повідомлення користувача
        await save_message(db, customer_id, "user", user_text)
        await increment_daily_usage(db, customer_id)
        await db.commit()

    # Індикатор "друкує..."
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        catalog = await get_catalog_context()
        system_with_catalog = f"{SYSTEM_PROMPT}\n\n{catalog}"

        # Будуємо список повідомлень (Groq використовує OpenAI-формат)
        messages = [{"role": "system", "content": system_with_catalog}]
        for h in history:
            # У БД роль "model" — в Groq це "assistant"
            role = "assistant" if h["role"] == "model" else h["role"]
            messages.append({"role": role, "content": h["parts"][0]})
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": messages,
            "max_tokens": 250,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers
            ) as resp:
                data = await resp.json()

        if "error" in data:
            raise Exception(data["error"].get("message", str(data["error"])))

        reply = data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        await message.answer(f"⚠️ Помилка: {e}")
        return

    # Зберегти відповідь AI
    async with aiosqlite.connect(DATABASE_URL) as db:
        await save_message(db, customer_id, "model", reply)
        await db.commit()

    await message.answer(reply)
