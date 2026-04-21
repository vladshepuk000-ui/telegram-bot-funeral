# Архітектура системи

## Загальна схема

```
Ти публікуєш пост у Telegram-канал
  │
  ▼
Парсер каналу (Telethon)
  │
  ├── розпізнає товар, ціну, фото
  └── автоматично оновлює БД
            │
            ▼
     SQLite / PostgreSQL ◄─────────────────────────┐
            │                                       │
            ▼                                       │
Telegram-бот (aiogram 3.x)                         │
  │                                                 │
  ├── Каталог товарів                               │
  ├── FSM замовлення ───────────────────────────────┘
  ├── AI-асистент (Claude API) ← відповідає на питання
  ├── FAQ (автовідповідь)
  └── Адмін-панель (команди)

APScheduler (читає з БД)
  ├── Розсилки по базі клієнтів
  ├── Нагадування клієнтам
  ├── Щотижневий звіт → тобі в Telegram
  └── Перевірка залишків товарів

Telethon (автопостинг)
  └── Публікація оголошень у групи регіону

FastAPI (Backend API)
  ├── /api/products  — товари для PWA і дашборду
  ├── /api/orders    — замовлення
  ├── /api/stats     — статистика
  └── /admin         — веб-дашборд (Jinja2)

PWA (Vue.js / React)
  ├── Каталог з фільтрами і фото
  ├── Корзина + оформлення замовлення
  ├── Статус замовлення
  └── Встановлюється на телефон як додаток
```

---

## База даних

### Таблиця `products`
```sql
id          INTEGER PRIMARY KEY
name        TEXT NOT NULL          -- назва товару
category    TEXT                   -- рідини / картриджі / системи
description TEXT                   -- опис
price       REAL NOT NULL          -- ціна
stock       INTEGER DEFAULT 0      -- кількість в наявності
photo_id    TEXT                   -- Telegram file_id (для бота)
photo_url   TEXT                   -- публічний URL фото (для PWA і дашборду)
is_active   BOOLEAN DEFAULT 1      -- показувати в каталозі
created_at  DATETIME
```

### Таблиця `customers`
```sql
id           INTEGER PRIMARY KEY
telegram_id    INTEGER UNIQUE NOT NULL
username       TEXT
phone          TEXT                   -- номер телефону (якщо поділився)
is_subscribed  BOOLEAN DEFAULT 1      -- чи отримує розсилки (/stop = 0)
first_seen     DATETIME
last_order     DATETIME
total_orders   INTEGER DEFAULT 0
```

### Таблиця `orders`
```sql
id           INTEGER PRIMARY KEY
customer_id  INTEGER REFERENCES customers(id)
address      TEXT                   -- адреса доставки (Нова Пошта)
notes        TEXT                   -- коментар клієнта
total_price  REAL                   -- підсумкова сума замовлення
status       TEXT DEFAULT 'new'     -- new / confirmed / sent / done
created_at   DATETIME
```

### Таблиця `waitlist` ← черга очікування товару
```sql
id           INTEGER PRIMARY KEY
customer_id  INTEGER REFERENCES customers(id)
product_id   INTEGER REFERENCES products(id)
created_at   DATETIME
```

### Таблиця `reviews` ← відгуки після отримання замовлення
```sql
id           INTEGER PRIMARY KEY
customer_id  INTEGER REFERENCES customers(id)
order_id     INTEGER REFERENCES orders(id)
rating       INTEGER NOT NULL       -- оцінка від 1 до 5
text         TEXT                   -- текст відгуку (необов'язково)
created_at   DATETIME
```

### Таблиця `broadcasts` ← логування розсилок
```sql
id           INTEGER PRIMARY KEY
text         TEXT NOT NULL          -- текст розсилки
sent_count   INTEGER DEFAULT 0      -- скільки клієнтів отримали
error_count  INTEGER DEFAULT 0      -- скільки помилок (заблокували бота)
created_at   DATETIME
```

### Таблиця `broadcast_templates` ← шаблони для авторозсилок
```sql
id           INTEGER PRIMARY KEY
text         TEXT NOT NULL          -- текст шаблону
used_count   INTEGER DEFAULT 0      -- скільки разів використано
last_used    DATETIME
```

### Таблиця `ai_usage` ← лічильник AI запитів на день
```sql
id           INTEGER PRIMARY KEY
customer_id  INTEGER REFERENCES customers(id)
date         DATE NOT NULL          -- поточна дата
count        INTEGER DEFAULT 0      -- кількість запитів за день
```

### Таблиця `ai_chat_history` ← контекст розмов з AI-асистентом
```sql
id           INTEGER PRIMARY KEY
customer_id  INTEGER REFERENCES customers(id)
role         TEXT NOT NULL          -- 'user' або 'assistant'
content      TEXT NOT NULL          -- текст повідомлення
created_at   DATETIME
```

### Таблиця `order_items` ← окрема, бо в замовленні може бути кілька товарів
```sql
id           INTEGER PRIMARY KEY
order_id     INTEGER REFERENCES orders(id)
product_id   INTEGER REFERENCES products(id)
quantity     INTEGER NOT NULL
price_at_order REAL NOT NULL        -- ціна на момент замовлення (фіксується!)
```

---

## FSM — Стани замовлення

```
/start
  │
  ▼
choosing_product    ← клієнт обирає товар з каталогу (можна кілька)
  │
  ▼
choosing_quantity   ← скільки одиниць
  │
  ▼
entering_address    ← адреса доставки (Нова Пошта: місто + відділення)
  │
  ▼
entering_phone      ← номер телефону для відділення НП
  │
  ▼
entering_notes      ← коментар (необов'язково, кнопка "Пропустити")
  │
  ▼
confirmation        ← показати підсумок + реквізити для оплати
                       кнопки "Підтвердити" / "Скасувати"
  │
  ▼
END → зберегти в БД
    → сповістити адміна (всі деталі)
    → сповістити клієнта (підтвердження + що далі)

/cancel — скидає FSM у будь-який момент
```

---

## Безпека

- `BOT_TOKEN` — тільки в `.env`
- `ADMIN_IDS` — тільки в `.env`
- Персональні дані (адреса, ім'я) — тільки в БД, не в логах
- `callback_data` — валідувати через `F.data ==` або `CallbackData`
- Адмін-команди перевіряють `message.from_user.id in ADMIN_IDS`
- `.env` в `.gitignore` — ніколи не комітити

---

## Деплой (безкоштовно)

### Railway
```bash
# Встановити Railway CLI
npm install -g @railway/cli

# Логін та деплой
railway login
railway init
railway up
```

### Render
- Підключити GitHub репозиторій
- Вибрати "Web Service" або "Background Worker"
- Додати змінні середовища (.env)
- Автодеплой при кожному git push
