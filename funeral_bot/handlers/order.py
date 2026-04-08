"""Хендлери оформлення замовлення через FSM."""
import logging
import re

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db.database import get_connection
from db import models
from keyboards.order_kb import (
    consent_keyboard, confirmation_keyboard, cancel_active_order_keyboard,
    burial_extras_keyboard, BURIAL_EXTRAS, BURIAL_EXTRAS_FROM,
    installation_extras_keyboard, INSTALLATION_EXTRAS, INSTALLATION_EXTRAS_FROM,
)
from keyboards.main_menu import BTN_ORDER, BTN_CATALOG, BTN_PACKAGES, BTN_EMERGENCY, BTN_STATUS, BTN_CONTACTS, main_menu
from states.order_states import OrderForm
from config import settings

logger = logging.getLogger(__name__)
router = Router()

# Валідація українського номера телефону
PHONE_RE = re.compile(r"^(\+?380|0)\d{9}$")

MONUMENT_NAMES = {
    "DE": "Дитячі ексклюзивні",
    "DS": "Дитячі класичні",
    "DK": "Дитячі комбіновані",
    "OE": "Одинарні ексклюзивні",
    "OS": "Одинарні класичні",
    "OK": "Одинарні комбіновані",
    "PE": "Подвійні ексклюзивні",
    "PS": "Подвійні класичні",
    "PK": "Подвійні комбіновані",
}

_MENU_BUTTONS = {BTN_ORDER, BTN_CATALOG, BTN_PACKAGES, BTN_EMERGENCY, BTN_STATUS, BTN_CONTACTS}


@router.message(StateFilter(OrderForm), F.text.in_(_MENU_BUTTONS))
async def interrupt_order_with_menu(message: Message, state: FSMContext) -> None:
    """Якщо під час FSM-форми натиснута кнопка меню — скасовуємо форму.

    Якщо замовлення вже створено в БД (крок підтвердження) — скасовуємо його,
    щоб не залишати фантомних pending-записів.
    """
    data = await state.get_data()
    order_id = data.get("order_id")
    if order_id:
        async with get_connection() as db:
            await models.cancel_order(db, order_id, message.from_user.id)

    await state.clear()
    await message.answer(
        "⚠️ Оформлення заявки перервано. Поверніться до меню або почніть знову.",
        reply_markup=main_menu,
    )

CONSENT_TEXT = (
    "📄 <b>Згода на обробку персональних даних</b>\n\n"
    "Для оформлення заявки нам необхідно отримати ваше ім'я, номер телефону "
    "та населений пункт. Ці дані використовуються виключно для зв'язку з вами "
    "щодо надання послуг.\n\n"
    "Ви погоджуєтесь на обробку ваших персональних даних?"
)

MANAGER_ORDER_TEXT = (
    "📋 <b>НОВА ЗАЯВКА #{order_id}</b>\n\n"
    "👤 Ім'я: {name}\n"
    "📞 Телефон: {phone}\n"
    "📍 Населений пункт: {city}\n"
    "{item_line}"
    "\n🆔 Telegram ID клієнта: {client_id}"
)


def _burial_summary_lines(extras: list) -> tuple[str, int]:
    """Повертає (рядки для повідомлення, загальна ціна)."""
    base = 8000
    extras_total = sum(BURIAL_EXTRAS[c][1] for c in extras if c in BURIAL_EXTRAS)
    total = base + extras_total
    lines = "".join(
        f"  ✅ {BURIAL_EXTRAS[c][0]} (+{'від ' if c in BURIAL_EXTRAS_FROM else ''}{BURIAL_EXTRAS[c][1]} грн)\n"
        for c in extras if c in BURIAL_EXTRAS
    ) or "  — без додаткових послуг\n"
    return lines, total


def _format_item_line(order: dict) -> str:
    if order.get("service_id"):
        return f"🕊 Послуга ID: {order['service_id']}\n"
    if order.get("product_id"):
        return f"🛒 Товар ID: {order['product_id']}\n"
    if order.get("package_id"):
        return f"📦 Пакет ID: {order['package_id']}\n"
    return ""


# ---------------------------------------------------------------------------
# Вхід у форму — через меню або з каталогу
# ---------------------------------------------------------------------------

async def _start_order_flow(
    message_or_callback: Message | CallbackQuery,
    state: FSMContext,
    **order_kwargs,
) -> None:
    """Запускає FSM-форму, зберігаючи обраний товар/послугу/пакет."""
    await state.update_data(**order_kwargs)

    user_id = message_or_callback.from_user.id
    async with get_connection() as db:
        has_consent = await models.has_consent(db, user_id)

    target = (
        message_or_callback
        if isinstance(message_or_callback, Message)
        else message_or_callback.message
    )

    if has_consent:
        await state.set_state(OrderForm.waiting_for_name)
        await target.answer("Введіть ваше ім'я:")
    else:
        await state.set_state(OrderForm.waiting_for_consent)
        await target.answer(
            CONSENT_TEXT, parse_mode="HTML", reply_markup=consent_keyboard()
        )



@router.callback_query(F.data.startswith("order_service:"))
async def order_service(callback: CallbackQuery, state: FSMContext) -> None:
    service_id = int(callback.data.split(":")[1])
    await callback.answer()
    await _start_order_flow(callback, state, service_id=service_id)


@router.callback_query(F.data.startswith("order_product:"))
async def order_product(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    await callback.answer()
    await _start_order_flow(callback, state, product_id=product_id)


@router.callback_query(F.data.startswith("order_package:"))
async def order_package(callback: CallbackQuery, state: FSMContext) -> None:
    package_id = int(callback.data.split(":")[1])
    await callback.answer()
    await _start_order_flow(callback, state, package_id=package_id)


@router.callback_query(F.data.startswith("order_monument:"))
async def order_monument(callback: CallbackQuery, state: FSMContext) -> None:
    _, code, idx_str = callback.data.split(":")
    monument_name = MONUMENT_NAMES.get(code, code)
    await callback.answer()
    await _start_order_flow(
        callback, state,
        monument_code=code,
        monument_name=monument_name,
        monument_photo_index=int(idx_str) + 1,
    )


@router.callback_query(OrderForm.waiting_for_extras, F.data == "back_to_burial")
async def back_to_burial(callback: CallbackQuery, state: FSMContext) -> None:
    from handlers.catalog import BURIAL_INFO_TEXT
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    await state.clear()
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Оформити замовлення", callback_data="order_burial")
    await callback.message.edit_text(
        BURIAL_INFO_TEXT, parse_mode="HTML", reply_markup=builder.as_markup()
    )


@router.callback_query(OrderForm.waiting_for_inst_extras, F.data == "back_to_installation")
async def back_to_installation(callback: CallbackQuery, state: FSMContext) -> None:
    from handlers.catalog import INSTALLATION_CAPTION
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    await state.clear()
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Оформити замовлення", callback_data="order_installation")
    await callback.message.edit_text(
        INSTALLATION_CAPTION, parse_mode="HTML", reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "order_burial")
async def order_burial(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(burial=True, burial_extras=[])
    await state.set_state(OrderForm.waiting_for_extras)
    await callback.message.answer(
        "➕ <b>Оберіть додаткові послуги</b> (можна кілька, або натисніть «Далі»):",
        parse_mode="HTML",
        reply_markup=burial_extras_keyboard(set()),
    )


@router.callback_query(F.data == "order_installation")
async def order_installation(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(installation=True, inst_extras=[])
    await state.set_state(OrderForm.waiting_for_inst_extras)
    await callback.message.answer(
        "➕ <b>Оберіть додаткові роботи</b> (можна кілька, або натисніть «Далі»):",
        parse_mode="HTML",
        reply_markup=installation_extras_keyboard(set()),
    )


@router.callback_query(OrderForm.waiting_for_inst_extras, F.data.startswith("inst_extra:"))
async def toggle_inst_extra(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("inst_extras", []))
    selected.discard(code) if code in selected else selected.add(code)
    await state.update_data(inst_extras=list(selected))
    await callback.message.edit_reply_markup(reply_markup=installation_extras_keyboard(selected))
    await callback.answer()


@router.callback_query(OrderForm.waiting_for_inst_extras, F.data == "inst_extras_done")
async def inst_extras_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    async with get_connection() as db:
        has_consent = await models.has_consent(db, callback.from_user.id)
    if has_consent:
        await state.set_state(OrderForm.waiting_for_name)
        await callback.message.answer("Введіть ваше ім'я:")
    else:
        await state.set_state(OrderForm.waiting_for_consent)
        await callback.message.answer(
            CONSENT_TEXT, parse_mode="HTML", reply_markup=consent_keyboard()
        )


@router.callback_query(OrderForm.waiting_for_extras, F.data.startswith("extra_toggle:"))
async def toggle_extra(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("burial_extras", []))
    if code in selected:
        selected.discard(code)
    else:
        selected.add(code)
    await state.update_data(burial_extras=list(selected))
    await callback.message.edit_reply_markup(reply_markup=burial_extras_keyboard(selected))
    await callback.answer()


@router.callback_query(OrderForm.waiting_for_extras, F.data == "extras_done")
async def extras_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    has_consent = False
    async with get_connection() as db:
        has_consent = await models.has_consent(db, callback.from_user.id)
    if has_consent:
        await state.set_state(OrderForm.waiting_for_name)
        await callback.message.answer("Введіть ваше ім'я:")
    else:
        await state.set_state(OrderForm.waiting_for_consent)
        await callback.message.answer(
            CONSENT_TEXT, parse_mode="HTML", reply_markup=consent_keyboard()
        )


# ---------------------------------------------------------------------------
# Крок 1: Згода на обробку персональних даних
# ---------------------------------------------------------------------------

@router.callback_query(OrderForm.waiting_for_consent, F.data == "consent:accept")
async def consent_accepted(callback: CallbackQuery, state: FSMContext) -> None:
    async with get_connection() as db:
        await models.set_consent(db, callback.from_user.id)
    await state.set_state(OrderForm.waiting_for_name)
    await callback.message.edit_text("✅ Дякуємо за підтвердження!")
    await callback.message.answer("Введіть ваше ім'я:")


@router.callback_query(OrderForm.waiting_for_consent, F.data == "consent:decline")
async def consent_declined(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "❌ Без згоди на обробку персональних даних оформлення заявки неможливе.\n\n"
        "Ви можете зателефонувати нам напряму або написати менеджеру."
    )


# ---------------------------------------------------------------------------
# Крок 2: Ім'я
# ---------------------------------------------------------------------------

@router.message(OrderForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2 or len(name) > 100:
        await message.answer("Введіть коректне ім'я (від 2 до 100 символів):")
        return
    await state.update_data(client_name=name)
    await state.set_state(OrderForm.waiting_for_phone)
    await message.answer(
        "Введіть ваш номер телефону (формат: +380XXXXXXXXX або 0XXXXXXXXX):"
    )


# ---------------------------------------------------------------------------
# Крок 3: Телефон
# ---------------------------------------------------------------------------

@router.message(OrderForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip().replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        await message.answer(
            "❗ Некоректний формат номеру.\n"
            "Введіть у форматі +380XXXXXXXXX або 0XXXXXXXXX:"
        )
        return
    await state.update_data(client_phone=phone)
    await state.set_state(OrderForm.waiting_for_city)
    await message.answer("Введіть назву вашого населеного пункту:")


# ---------------------------------------------------------------------------
# Крок 4: Населений пункт → зберігаємо заявку → показуємо підсумок
# ---------------------------------------------------------------------------

@router.message(OrderForm.waiting_for_city)
async def process_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    if len(city) < 2 or len(city) > 100:
        await message.answer("Введіть коректну назву населеного пункту:")
        return

    data = await state.get_data()
    await state.update_data(client_city=city)

    # Зберігаємо заявку, щоб отримати ID для кнопок підтвердження/скасування
    async with get_connection() as db:
        order_id = await models.create_order(
            db,
            client_id=message.from_user.id,
            client_name=data["client_name"],
            client_phone=data["client_phone"],
            client_city=city,
            service_id=data.get("service_id"),
            product_id=data.get("product_id"),
            package_id=data.get("package_id"),
        )

    await state.update_data(order_id=order_id)
    await state.set_state(OrderForm.waiting_for_confirmation)

    item_summary = ""
    total_price = None

    if data.get("monument_name"):
        item_summary = f"🪨 Памятник: {data['monument_name']}, фото №{data.get('monument_photo_index', '?')}\n"

    elif data.get("burial"):
        extras = data.get("burial_extras", [])
        extras_lines, total_price = _burial_summary_lines(extras)
        item_summary = (
            f"🕊️ Послуги поховання\n"
            f"  📦 Базовий пакет: 8 000 грн\n"
            f"{extras_lines}"
            f"  💰 <b>Разом: від {total_price} грн</b>\n"
        )

    elif data.get("installation"):
        extras = data.get("inst_extras", [])
        base = 8000
        extras_total = sum(INSTALLATION_EXTRAS[c][1] for c in extras if c in INSTALLATION_EXTRAS)
        total_price = base + extras_total
        extras_lines = "".join(
            f"  ✅ {INSTALLATION_EXTRAS[c][0]} (+від {INSTALLATION_EXTRAS[c][1]} грн)\n"
            for c in extras if c in INSTALLATION_EXTRAS
        ) or "  — без додаткових робіт\n"
        item_summary = (
            f"🪦 Встановлення пам'ятника\n"
            f"  🏗️ Стандартна установка: 8 000 грн\n"
            f"{extras_lines}"
            f"  💰 <b>Разом: від {total_price} грн</b>\n"
        )

    summary = (
        "📋 <b>Перевірте ваші дані:</b>\n\n"
        f"👤 Ім'я: {data['client_name']}\n"
        f"📞 Телефон: {data['client_phone']}\n"
        f"📍 Населений пункт: {city}\n"
        f"{item_summary}\n"
        "Підтверджуєте замовлення?"
    )
    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=confirmation_keyboard(order_id),
    )


# ---------------------------------------------------------------------------
# Крок 5: Підтвердження
# ---------------------------------------------------------------------------

@router.callback_query(OrderForm.waiting_for_confirmation, F.data.startswith("confirm_order:"))
async def confirm_order(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    order_id = int(callback.data.split(":")[1])

    async with get_connection() as db:
        order = await models.get_order(db, order_id)
        if not order:
            await callback.answer("Заявку не знайдено.", show_alert=True)
            await state.clear()
            return
        await models.update_order_status(db, order_id, "confirmed")

    fsm_data = await state.get_data()
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Заявку #{order_id} підтверджено!</b>\n\n"
        "Менеджер зв'яжеться з вами найближчим часом для уточнення деталей.\n\n"
        "Ви можете скасувати заявку до дзвінка менеджера:",
        parse_mode="HTML",
        reply_markup=cancel_active_order_keyboard(order_id),
    )
    await callback.message.answer("Головне меню:", reply_markup=main_menu)

    # Сповіщення менеджеру
    if fsm_data.get("monument_name"):
        item_line = (
            f"🪨 Памятник: {fsm_data['monument_name']} ({fsm_data.get('monument_code', '')}), "
            f"фото №{fsm_data.get('monument_photo_index', '?')}\n"
        )
    elif fsm_data.get("burial"):
        extras = fsm_data.get("burial_extras", [])
        extras_lines, total = _burial_summary_lines(extras)
        item_line = (
            f"🕊️ Послуги поховання\n"
            f"  📦 Базовий пакет: 8 000 грн\n"
            f"{extras_lines}"
            f"  💰 Разом: від {total} грн\n"
        )
    elif fsm_data.get("installation"):
        extras = fsm_data.get("inst_extras", [])
        base = 8000
        extras_total = sum(INSTALLATION_EXTRAS[c][1] for c in extras if c in INSTALLATION_EXTRAS)
        total = base + extras_total
        extras_lines = "".join(
            f"  ✅ {INSTALLATION_EXTRAS[c][0]} (+від {INSTALLATION_EXTRAS[c][1]} грн)\n"
            for c in extras if c in INSTALLATION_EXTRAS
        ) or "  — без додаткових робіт\n"
        item_line = (
            f"🪦 Встановлення пам'ятника\n"
            f"  🏗️ Стандартна установка: 8 000 грн\n"
            f"{extras_lines}"
            f"  💰 Разом: від {total} грн\n"
        )
    else:
        item_line = _format_item_line(order)

    manager_text = MANAGER_ORDER_TEXT.format(
        order_id=order_id,
        name=order["client_name"],
        phone=order["client_phone"],
        city=order["client_city"],
        item_line=item_line,
        client_id=order["client_id"],
    )
    try:
        await bot.send_message(
            chat_id=settings.MANAGER_CHAT_ID,
            text=manager_text,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Не вдалося надіслати сповіщення менеджеру: %s", e)

    logger.info("Нова заявка #%d від user_id=%d", order_id, callback.from_user.id)


# ---------------------------------------------------------------------------
# Скасування під час заповнення форми
# ---------------------------------------------------------------------------

@router.callback_query(OrderForm.waiting_for_confirmation, F.data.startswith("cancel_order:"))
async def cancel_during_form(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    order_id = int(callback.data.split(":")[1])

    # Беремо дані клієнта зі стану до його очищення
    data = await state.get_data()
    client_name  = data.get("client_name", "—")
    client_phone = data.get("client_phone", "—")

    async with get_connection() as db:
        await models.cancel_order(db, order_id, callback.from_user.id)

    await state.clear()

    # Сповіщення менеджеру
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"⚠️ Клієнт {client_name} ({client_phone}) "
                    f"скасував замовлення #{order_id} в процесі оформлення."
                ),
            )
        except Exception as e:
            logger.error("Не вдалося сповістити адміна %d: %s", admin_id, e)

    await callback.message.edit_text(
        f"❌ Заявку #{order_id} скасовано. Повертайтесь, коли будете готові."
    )
    await callback.message.answer("Головне меню:", reply_markup=main_menu)
    logger.info("Заявку #%d скасовано клієнтом %d під час форми", order_id, callback.from_user.id)


# ---------------------------------------------------------------------------
# Скасування вже підтвердженої заявки (до дзвінка менеджера)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_confirmed_order(callback: CallbackQuery, bot: Bot) -> None:
    order_id = int(callback.data.split(":")[1])

    async with get_connection() as db:
        # Беремо дані до скасування, поки запис ще active
        order = await models.get_order(db, order_id)
        success = await models.cancel_order(db, order_id, callback.from_user.id)

    if success:
        await callback.message.edit_text(f"❌ Заявку #{order_id} скасовано.")

        # Сповіщення менеджеру з даними клієнта з БД
        client_name  = order["client_name"]  if order else "—"
        client_phone = order["client_phone"] if order else "—"
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"⚠️ Клієнт {client_name} ({client_phone}) "
                        f"скасував підтверджену заявку #{order_id}."
                    ),
                )
            except Exception as e:
                logger.error("Не вдалося сповістити адміна %d: %s", admin_id, e)

        logger.info("Заявку #%d скасовано клієнтом %d", order_id, callback.from_user.id)
    else:
        await callback.answer(
            "Не вдалося скасувати. Можливо, менеджер вже опрацьовує заявку — зателефонуйте нам.",
            show_alert=True,
        )
