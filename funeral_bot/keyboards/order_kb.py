"""Клавіатури для процесу оформлення замовлення."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Додаткові послуги поховання: код -> (назва, ціна)
BURIAL_EXTRAS = {
    "morgue":   ("🚐 Перевезення до/з моргу",       500),
    "tent":     ("🏛️ Намет + ритуальні столики",    500),
    "demolish": ("🛠️ Демонтаж старих конструкцій",  500),
    "clearing": ("🌳 Спилювання дерев/чагарників",   800),
}

# Послуги з ціною «від»
BURIAL_EXTRAS_FROM = {"demolish", "clearing"}

# Додаткові послуги встановлення пам'ятників: код -> (назва, ціна)
INSTALLATION_EXTRAS = {
    "demolish_mon": ("🛠️ Демонтаж",                    1000),
    "trot":         ("🧱 Тротуарна плитка",             3000),
    "oblic":        ("✨ Облицювальна плитка",           8000),
}

# Всі ціни «від»
INSTALLATION_EXTRAS_FROM = {"demolish_mon", "trot", "oblic"}


def installation_extras_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, (name, price) in INSTALLATION_EXTRAS.items():
        mark = "✅ " if code in selected else ""
        builder.button(
            text=f"{mark}{name} (+від {price} грн)",
            callback_data=f"inst_extra:{code}",
        )
        builder.adjust(1)
    builder.button(text="➡️ Далі", callback_data="inst_extras_done")
    builder.button(text="↩ Назад", callback_data="back_to_installation")
    builder.adjust(1)
    return builder.as_markup()


def _price_label(code: str, price: int) -> str:
    prefix = "від " if code in BURIAL_EXTRAS_FROM else ""
    return f"+{prefix}{price} грн"


def burial_extras_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    """Вибір додаткових послуг з чекбоксами. selected — множина обраних кодів."""
    builder = InlineKeyboardBuilder()
    for code, (name, price) in BURIAL_EXTRAS.items():
        mark = "✅ " if code in selected else ""
        builder.button(
            text=f"{mark}{name} ({_price_label(code, price)})",
            callback_data=f"extra_toggle:{code}",
        )
        builder.adjust(1)
    builder.button(text="➡️ Далі", callback_data="extras_done")
    builder.button(text="↩ Назад", callback_data="back_to_burial")
    builder.adjust(1)
    return builder.as_markup()


def consent_keyboard() -> InlineKeyboardMarkup:
    """Кнопки підтвердження згоди на обробку персональних даних."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Погоджуюсь", callback_data="consent:accept")
    builder.button(text="❌ Відмовляюсь", callback_data="consent:decline")
    builder.adjust(2)
    return builder.as_markup()


def confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Кнопки підтвердження або скасування заявки перед відправкою."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Підтвердити", callback_data=f"confirm_order:{order_id}")
    builder.button(text="❌ Скасувати", callback_data=f"cancel_order:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def cancel_active_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Кнопка скасування вже відправленої заявки (до дзвінка менеджера)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Скасувати заявку", callback_data=f"cancel_order:{order_id}")
    builder.adjust(1)
    return builder.as_markup()
