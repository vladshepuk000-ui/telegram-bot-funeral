"""Регресійні тести для BUG-1..BUG-5."""
import importlib
import pytest

from keyboards.main_menu import (
    BTN_CONTACTS, BTN_CATALOG, BTN_PACKAGES, BTN_ORDER, BTN_STATUS, BTN_EMERGENCY,
)
from handlers.order import _MENU_BUTTONS


# ---------------------------------------------------------------------------
# BUG-1: /start більше не використовує settings.WORK_HOUR_START/END
# ---------------------------------------------------------------------------

def test_start_handler_has_no_working_hours_check():
    """start.py не повинен імпортувати чи використовувати WORK_HOUR_*."""
    import inspect
    import handlers.start as start_module
    source = inspect.getsource(start_module)
    assert "WORK_HOUR" not in source, (
        "start.py містить WORK_HOUR — бот має працювати цілодобово"
    )


def test_start_module_imports_cleanly():
    """handlers.start імпортується без AttributeError."""
    import handlers.start  # не повинно кидати виключень


# ---------------------------------------------------------------------------
# BUG-2: BTN_CONTACTS є у _MENU_BUTTONS
# ---------------------------------------------------------------------------

def test_contacts_button_in_menu_buttons():
    """BTN_CONTACTS має бути в _MENU_BUTTONS, щоб FSM не ковтала натискання."""
    assert BTN_CONTACTS in _MENU_BUTTONS, (
        f"BTN_CONTACTS ({BTN_CONTACTS!r}) відсутній у _MENU_BUTTONS"
    )


def test_all_main_menu_buttons_in_menu_buttons():
    """Усі кнопки головного меню мають бути в _MENU_BUTTONS."""
    all_buttons = {BTN_CATALOG, BTN_PACKAGES, BTN_ORDER, BTN_STATUS, BTN_EMERGENCY, BTN_CONTACTS}
    missing = all_buttons - _MENU_BUTTONS
    assert not missing, f"Ці кнопки відсутні у _MENU_BUTTONS: {missing}"


@pytest.mark.asyncio
async def test_contacts_button_clears_fsm_state():
    """Натискання BTN_CONTACTS під час FSM очищує стан."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.context import FSMContext
    from states.order_states import OrderForm
    from handlers.order import interrupt_order_with_menu

    storage = MemoryStorage()
    key = StorageKey(bot_id=0, chat_id=1, user_id=1)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(OrderForm.waiting_for_phone)

    msg = MagicMock()
    msg.text = BTN_CONTACTS
    msg.from_user = MagicMock()
    msg.from_user.id = 1
    msg.answer = AsyncMock()

    await interrupt_order_with_menu(msg, state)

    assert await state.get_state() is None


# ---------------------------------------------------------------------------
# BUG-3: catalog_back більше не викликає _catalog_section_kb()
# ---------------------------------------------------------------------------

def test_catalog_back_has_no_catalog_section_kb_call():
    """catalog_back не повинен викликати _catalog_section_kb — функції не існує."""
    import inspect
    import handlers.catalog as catalog_module
    source = inspect.getsource(catalog_module.catalog_back)
    assert "_catalog_section_kb" not in source, (
        "catalog_back досі викликає _catalog_section_kb() — це призведе до NameError"
    )


def test_catalog_module_has_no_undefined_catalog_section_kb():
    """_catalog_section_kb не визначена і не повинна викликатися."""
    import handlers.catalog as catalog_module
    assert not hasattr(catalog_module, "_catalog_section_kb"), (
        "_catalog_section_kb визначена в catalog.py — чи це навмисно?"
    )


# ---------------------------------------------------------------------------
# BUG-4: conftest використовує _SCHEMA коректно (список, не рядок)
# ---------------------------------------------------------------------------

def test_schema_is_list():
    """_SCHEMA повинна бути списком рядків (не одним рядком)."""
    from db.database import _SCHEMA
    assert isinstance(_SCHEMA, list), f"_SCHEMA має бути list, а не {type(_SCHEMA)}"
    assert all(isinstance(s, str) for s in _SCHEMA), "_SCHEMA має містити лише рядки"


@pytest.mark.asyncio
async def test_conftest_db_fixture_works(db):
    """Фікстура db з conftest.py ініціалізується без помилок."""
    # Якщо fixture не зламана — цей тест просто проходить
    async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        tables = {row[0] for row in await cur.fetchall()}
    assert "clients" in tables
    assert "orders" in tables
    assert "monument_photos" in tables


# ---------------------------------------------------------------------------
# BUG-5: faq.py імпортується без ImportError
# ---------------------------------------------------------------------------

def test_faq_module_imports_cleanly():
    """handlers.faq більше не падає з ImportError через BTN_FAQ."""
    import handlers.faq  # не повинно кидати ImportError


def test_faq_btn_is_defined():
    """BTN_FAQ визначений всередині faq.py."""
    import handlers.faq as faq_module
    assert hasattr(faq_module, "BTN_FAQ")
