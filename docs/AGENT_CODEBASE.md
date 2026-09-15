# Справочник кодовой базы для AI-агентов

Документ описывает **что умеет проект**, **где лежит логика** и **какие API вызывать**. Цель — не подгружать весь репозиторий на каждую задачу. Актуальные решения команды — в [`MEMORY.md`](MEMORY.md); структурный граф — `graphify-out/` + `graphify query`.

---

## 1. Назначение продукта

**Telegram Shop Bot** — продажа **цифровых товаров** (ключи, аккаунты и т.д.) через Telegram.

| Роль | Возможности |
|------|-------------|
| Пользователь | Каталог, поиск (trigram), корзина с количеством, промокоды, оплата баланса / Stars / fiat / CryptoPay, покупки, отзывы, рефералы, подписка на restock |
| Админ (чат) | CRUD каталога, склад, пользователи, баланс, роли (битовые права), промо, распродажи, рассылки, статистика — по `Permission` |
| Админ (веб) | SQLAdmin на `/admin`, CSV export, restock с уведомлением ожидающих |
| Система | Аудит, метрики, recovery зависших CryptoPay, retention, кэш Redis (опционально) |

Деньги в БД: **`NUMERIC(12,2)`**, не float.

---

## 2. Запуск и границы процесса

| Точка | Файл | Роль |
|-------|------|------|
| Entry | `run.py` | `load_dotenv` → `asyncio.run(start_bot)` |
| Lifecycle | `bot/main.py` | `start_bot()`: Bot, Dispatcher, middleware, polling/webhook, uvicorn admin, фоновые задачи |
| Конфиг | `bot/misc/env.py` | `EnvKeys` — все переменные окружения (класс с `Final` полями) |
| Схема БД | `migrations/` + `alembic.ini` | Миграции **обязательны** (`alembic upgrade head`) |
| Тесты | `tests/` | pytest; фабрики в `tests/factories.py` |

**Один asyncio-процесс:** бот + Starlette (админка) + `RecoveryManager` + `CleanupManager` + `CacheScheduler`.

**Порядок middleware** (внешний → внутренний): `RateLimit` → `Analytics` → `Auth` → `Security` → роутеры (`admin` → `other` → `user`).

---

## 3. Роутинг handlers

Регистрация: `bot/handlers/main.py` → `register_all_handlers(dp)`.

### 3.1 Пользователь (`bot/handlers/user/`)

| Модуль | Ответственность | Ключевые зависимости |
|--------|----------------|----------------------|
| `main.py` | `/start`, меню, профиль, подписка на канал, правила | `create_user`, `check_user`, клавиатуры |
| `shop_and_goods.py` | Категории, товары, поиск, карточка товара, промо на товаре, отзывы, restock subscribe, история покупок | `lazy_queries`, `add_to_cart`, FSM `ShopStates`, `ReviewFSM` |
| `cart.py` | Корзина, +/- qty, checkout, чек | `checkout_cart_transaction`, `_cart_view_data` |
| `balance_and_payment.py` | Пополнение, pre_checkout, successful_payment, CryptoPay | `payment.py`, `process_payment_with_referral`, `BalanceStates` |
| `referral_system.py` | Реферальная ссылка, списки, начисления | `lazy_queries`, пагинация |

### 3.2 Админ (`bot/handlers/admin/`)

| Модуль | Ответственность |
|--------|-----------------|
| `main.py` | Вход в админ-консоль, maintenance |
| `categories_management.py` | Категории CRUD |
| `adding_position.py` | Создание товара |
| `update_position.py` | Редактирование товара |
| `goods_management.py` | Склад (item_values), bulk values |
| `shop_management.py` | Статистика, кэш stats |
| `sale_management.py` | Скидки на товар (`sale_percent` / `sale_until`) |
| `promo_management.py` | Промокоды |
| `user_management.py` | Поиск пользователя, блок, баланс, рефералы |
| `role_management.py` | Роли и права |
| `broadcast.py` | Рассылка |

Фильтры прав: `bot/filters/main.py` — `HasPermissionFilter`, `HasAnyPermissionFilter`, `ValidAmountFilter`.

### 3.3 Прочее (`bot/handlers/other.py`)

Утилиты: `close`, `dummy_button`, `check_sub_channel`, `_any_payment_method_enabled`, `display_name`, `caller_name`, `generate_short_hash`.

---

## 4. Слой данных

### 4.1 Подключение

| Класс | Файл | Методы |
|-------|------|--------|
| `Database` (singleton) | `bot/database/main.py` | `session()` — async context manager, commit/rollback; `engine`, `dispose()` |
| `Base` | там же | SQLAlchemy 2.0 `DeclarativeBase` |
| `dsn()` | `bot/database/dsn.py` | URL для asyncpg |

### 4.2 ORM-модели (`bot/database/models/main.py`)

| Модель | Таблица | Назначение |
|--------|---------|------------|
| `Permission` | — (константы битов) | `USE`, `BROADCAST`, `SETTINGS_MANAGE`, `USERS_MANAGE`, `CATALOG_MANAGE`, `ADMINS_MANAGE`, `OWN`, `STATS_VIEW`, `BALANCE_MANAGE`, `PROMO_MANAGE`; хелперы `granted()`, `is_subset()` |
| `Role` | `roles` | Имя, `permissions` int, `default`; `insert_roles()` сиды USER/ADMIN/OWNER |
| `User` | `users` | PK `telegram_id`, `balance`, `role_id`, `referral_id`, `is_blocked` |
| `Categories` | `categories` | |
| `Goods` | `goods` | Цена, описание, `category_id`, `sale_percent`, `sale_until` |
| `ItemValues` | `item_values` | Склад: `value`, `is_infinity` (безлимитная выдача одного value) |
| `BoughtGoods` | `bought_goods` | История: снимок имени, value, цена за единицу, `unique_id` |
| `Operations` | `operations` | Леджер баланса (+/-) |
| `Payments` | `payments` | Внешние пополнения; unique `(provider, external_id)` |
| `ReferralEarnings` | `referral_earnings` | Комиссия реферера |
| `AuditLog` | `audit_log` | **Без FK на user** — лог переживает удаление |
| `PromoCodes` | `promo_codes` | `discount_type`: percent/fixed/balance; `scope` global/category/item |
| `PromoCodeUsages` | `promo_code_usages` | Один раз на пользователя на промо |
| `CartItems` | `cart_items` | `user_id`+`item_id` unique, `quantity`, `promo_code` на строку |
| `Reviews` | `reviews` | 1 отзыв на user+item |
| `StockSubscriptions` | `stock_subscriptions` | Ожидание restock |

`register_models()` → только `Role.insert_roles()`.

### 4.3 Методы БД (`bot/database/methods/`)

Используйте эти модули вместо прямого SQL в handlers.

#### `create.py` — создание

| Функция | Действие |
|---------|----------|
| `create_user` | Новый пользователь + referral |
| `create_item` / `create_category` | Каталог |
| `add_values_to_item` / `add_values_bulk` / `normalize_values` | Пополнение склада |
| `create_pending_payment` | Запись ожидающего платежа |
| `create_role` / `create_promo_code` | Админ-сущности |
| `add_to_cart` | Корзина (лимит `CART_MAX_QTY_PER_ITEM`) |
| `subscribe_to_stock` | Подписка на товар |
| `create_review` | Отзыв |

#### `read.py` — чтение и валидация (ядро домена)

| Группа | Функции |
|--------|---------|
| Пользователь | `check_user`, `check_role`, `get_user_profile_aggregates`, `is_user_blocked`, `get_user_referral`, `check_user_referrals` |
| Каталог | `get_item_info`, `get_items_info`, `check_category`, `select_item_values_amount`, `check_value` |
| Статистика | `get_user_count`, `select_*_orders`, `select_admins`, … |
| Кэш-обёртки | `*_cached` + `invalidate_*_cache` |
| Промо | `get_promo_code`, `promo_rule_error`, `validate_promo_for_item`, `validate_promos_for_cart` |
| Корзина | `get_cart_items`, `get_cart_count` |
| Отзывы | `get_item_avg_rating`, `has_purchased_item`, `get_user_review` |

`promo_rule_error` — канонические коды ошибок для покупки/редима.

#### `update.py` — изменения

`set_role`, `update_item`, `set_item_sale`, `set_user_blocked`, `set_cart_item_quantity`, `clear_cart_item_promo`, `update_category`, `update_role`, `toggle_promo_code`.

#### `delete.py` — удаление

`delete_item`, `delete_category`, `delete_role`, `delete_promo_code`, `remove_from_cart`, `clear_cart`, `unsubscribe_from_stock`, `pop_stock_subscribers`, `delete_review`, …

#### `lazy_queries.py` — пагинация для UI

`query_categories`, `query_items_in_category`, `query_goods_search`, `query_user_bought_items`, `query_all_users`, `query_promo_codes`, `query_user_operations_history`, `query_item_reviews`, … — везде `offset`/`limit`/`count_only`.

#### `pricing.py` — цены (чистые функции)

| Функция | Назначение |
|---------|------------|
| `effective_price(goods, now)` | Цена с учётом активной распродажи → `(price, on_sale, original)` |
| `apply_promo_discount` | percent/fixed с клампами |
| `coerce_sale_until` | Парсинг даты окончания sale |

#### `transactions.py` — атомарные операции (**критично для денег**)

| Функция | Назначение |
|---------|------------|
| `buy_item_transaction` | Покупка 1 товара: lock user+goods, списание, выдача value, bought_goods, referral, promo usage |
| `checkout_cart_transaction` | Мульти-позиционный checkout; сплит суммы по единицам `_split_amount` |
| `process_payment_with_referral` | Зачисление пополнения + referral на пополнение |
| `redeem_balance_promo` | Промо типа balance |
| `admin_balance_change` | Ручное изменение баланса админом |
| `replace_item_stock_and_meta` | Замена склада/метаданных товара (админ) |

При изменении цен/промо/корзины сверяйте логику с `cart._cart_view_data` — UI должен совпадать с транзакцией.

#### `audit.py`

| Символ | Назначение |
|--------|------------|
| `AuditBuffer` | Батчевая запись в `audit_log` |
| `log_audit` / `log_audit_bg` | Синхронный файл + async буфер |
| `start_audit_buffer` / `stop_audit_buffer` | Lifecycle в `main.py` |

#### `cache_utils.py`

`safe_create_task`, `drain_background_tasks` — фоновые инвалидации без падения loop.

---

## 5. Инфраструктура

### 5.1 Middleware (`bot/middleware/`)

| Класс | Файл | Роль |
|-------|------|------|
| `RateLimitMiddleware` | `rate_limit.py` | Глобальный и per-action лимит; Redis или in-memory |
| `AuthenticationMiddleware` | `security.py` | Кэш роли/блокировки; `resolve_role_cached`, `invalidate_auth_caches` |
| `SecurityMiddleware` | `security.py` | Maintenance, replay guard (~1h), подозрительные паттерны, аудит |

### 5.2 Кэш (`bot/misc/caching/`)

| Компонент | Назначение |
|-----------|------------|
| `CacheManager` | Redis get/set, декоратор `cache_result`, `single_flight` |
| `CacheScheduler` | Периодическая инвалидация stats, daily cleanup |
| `StatsCache` | Агрегаты для админ-статистики |
| `get_redis_storage` | FSM `RedisStorage` или fallback `MemoryStorage` |

### 5.3 Сервисы (`bot/misc/services/`)

| Модуль | Класс/функции | Назначение |
|--------|---------------|------------|
| `payment.py` | `send_stars_invoice`, `send_fiat_invoice`, CryptoPay helpers | Инвойсы Telegram |
| `recovery.py` | `RecoveryManager` | Каждые 5 мин — pending CryptoPay; 60 с — health DB/Redis |
| `cleanup.py` | `CleanupManager` | Retention audit/payments |
| `broadcast_system.py` | `BroadcastManager` | Массовая рассылка с rate limit |
| `restock_notifier.py` | `notify_restock` | После пополнения склада — сообщение подписчикам |

### 5.4 Прочее `bot/misc/`

| Файл | Назначение |
|------|------------|
| `lazy_paginator.py` | `LazyPaginator` — callback-пагинация |
| `validators.py` | Валидация ввода |
| `metrics.py` | `AnalyticsMiddleware`, Prometheus/JSON metrics |
| `singleton.py` | `SingletonMeta` для `Database` |

### 5.5 Веб (`bot/web/`)

| Файл | Назначение |
|------|------------|
| `admin.py` | `create_admin_app`: SQLAdmin views, `/health`, `/metrics`, login rate limit; `set_notifier_bot` для restock из панели |
| `export.py` | CSV: users, purchases, operations, payments |

Admin views наследуют `AuditModelView` где нужен аудит при изменениях.

### 5.6 UI и i18n

| Модуль | Назначение |
|--------|------------|
| `bot/keyboards/inline.py` | Все inline-клавиатуры, `lazy_paginated_keyboard` |
| `bot/i18n/main.py` | `localize(key, **kwargs)`, `esc()` для HTML |
| `bot/i18n/strings.py` | Словари ru/en |

### 5.7 FSM (`bot/states/`)

| StatesGroup | Использование |
|-------------|---------------|
| `ShopStates` | Навигация магазина, поиск |
| `ReviewFSM` | Текст отзыва |
| `BalanceStates` | Сумма пополнения |
| `GoodsFSM`, `AddItemFSM`, `UpdateItemFSM`, `SaleFSM` | Админ каталог |
| `CategoryFSM`, `PromoFSM`, `RoleMgmtFSM`, `UserMgmtStates`, `BroadcastFSM` | Админ |

---

## 6. Ключевые сценарии (куда смотреть)

### 6.1 Регистрация пользователя

`handlers/user/main.py` → `create_user` → роль USER по умолчанию; `OWNER_ID` из env получает OWNER при старте (см. admin bootstrap в main).

### 6.2 Покупка одного товара

Handler в `shop_and_goods.py` → `buy_item_transaction` → инвалидация кэшей → выдача value пользователю в сообщении.

### 6.3 Корзина и checkout

`cart.py` → `checkout_cart_transaction` — единственная точка списания за корзину; промо: одна строка на код (см. `validate_promos_for_cart`).

### 6.4 Пополнение баланса

`balance_and_payment.py` → invoice → `successful_payment` / CryptoPay callback → `process_payment_with_referral` → `Payments` idempotent.

### 6.5 Restock

Добавление `ItemValues` (бот или `ItemValuesAdmin`) → инвалидация stock cache → `notify_restock(bot, item_name)`.

### 6.6 Права админа

`AuthenticationMiddleware` + `HasPermissionFilter(Permission.XXX)` на хендлерах; веб-панель — отдельная сессия SQLAdmin.

---

## 7. Hub-узлы графа (ориентиры)

По `graphify god-nodes` наиболее связанные символы:

- `Database`, `localize()`, `log_audit()` — инфраструктура
- `buy_item_transaction`, `checkout_cart_transaction`, `process_payment_with_referral` — деньги
- `add_to_cart`, `get_item_info`, `PromoCodes` — каталог и промо
- `AuthenticationMiddleware`, `EnvKeys` — доступ и конфиг

Запрос: `graphify path "checkout_cart_transaction" "ItemValues"`.

---

## 8. Что менять для типичных задач

| Задача | Где править |
|--------|-------------|
| Новая кнопка в меню | `keyboards/inline.py`, handler в `user/main.py` или модуль фичи |
| Новое поле товара | модель `Goods`, alembic migration, `create`/`update`/`read`, admin handler + SQLAdmin |
| Новый способ оплаты | `payment.py`, `balance_and_payment.py`, `Payments` provider string, recovery если async |
| Новое админ-право | бит в `Permission`, `Role.insert_roles`, фильтры на handlers, веб — вручную ограничить view |
| Изменение цены/промо | **сначала** `pricing.py` + `transactions.py`, затем `cart._cart_view_data` |
| Кэш сломался | `invalidate_*` в `read.py`, вызовы после CRUD в methods |

**Не делать:** списание баланса в handler без транзакции в `transactions.py`.

---

## 9. Тесты (кратко)

| Область | Примеры файлов |
|---------|----------------|
| Транзакции | `test_transactions.py`, `test_cart_reviews.py` |
| Промо | `test_promo_validation.py`, `test_promo_management.py` |
| Middleware | `test_middleware.py`, `test_login_rate_limiter.py` |
| Admin handlers | `test_admin_handlers.py`, `test_goods_management.py` |
| Export / metrics | `test_export.py`, `test_metrics.py` |

Запуск: `pytest` из корня (см. `pytest.ini`, `conftest.py`).

---

## 10. Порядок чтения для нового агента

1. Этот файл + [`MEMORY.md`](MEMORY.md) (контекст команды).
2. `graphify query "<ваша фича>"` или `GRAPH_REPORT.md`.
3. Один сценарий end-to-end: handler → `database/methods` → модель.
4. Полный файл — только для редактирования.

После merge в `main`: `./devtools/graphify/refresh-after-merge.sh` (skill `/pr-memory-graphify`).

---

*Сгенерировано для репозитория Telegram Shop Bot; при крупных рефакторингах обновляйте разделы 4–6 и пересобирайте Graphify.*
