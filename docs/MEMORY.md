# Память проекта (журнал работ)

Этот файл — **единый источник контекста** для команды и для AI-агентов: что делаем, что обсуждаем, что получилось.  
Обновляйте его по ходу работы (короткие записи с датой лучше длинных отчётов).

## Как вести журнал

- **Решения** — что выбрали и почему (1–3 предложения).
- **Обсуждения** — варианты и вопросы по ходу работы.
- **Отвергли** — идеи, от которых отказались, и кратко почему (чтобы не возвращаться без причины).
- **Результаты** — что смержено, как проверить, ссылки на PR/коммиты.
- **Граф кода (Graphify)** — пересборка **после merge в `main`**: `./devtools/graphify/refresh-after-merge.sh` (см. skill `/pr-memory-graphify`).

**Ритуал:** PR готов → запись в MEMORY в ветке PR; PR смержен → обновить `graphify-out/` на `main`.

---

## 2026-09-17 — PR #14: ТЗ-09 — тикеты поддержки

**Ветка:** `cursor/support-tickets-tz09-03eb` → `main`  
**PR:** https://github.com/lexa97/telegram-shop/pull/14

### Сделали

- Модели `SupportTicket` / `SupportMessage`, миграция `e0f1a2b3c4d5` (revises `d8e9f0a1b2c3` после merge с ТЗ-08 в `main`).
- `TICKETS_MANAGE` = 1<<11 в матрице ТЗ-08; OPERATOR уже имеет тикеты в `insert_roles()`.
- User/admin handlers, SQLAdmin list views; `tests/test_support_tz09.py`.

### Проверка

- `pytest tests/test_support_tz09.py`
- `pytest`

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-17 — ТЗ-08: роли SUPERADMIN / ADMIN / OPERATOR / MANAGER

**Ветка:** смержено в `main` (PR #13)

### Сделали

- Новые биты: `ORDERS_MANAGE`, `TICKETS_MANAGE`, `PROVIDERS_MANAGE`, `PAYMENTS_CONFIG`, `AUDIT_VIEW`; `Permission.all_bits()`.
- `Role.insert_roles()`: USER, OPERATOR, MANAGER, ADMIN, SUPERADMIN; rename `OWNER` → `SUPERADMIN`.
- Миграция `d8e9f0a1b2c3`; `bot/database/role_names.py`; тесты `tests/test_rbac_tz08.py`.

### Матрица (биты)

| Роль | Назначение |
|------|------------|
| USER | USE |
| OPERATOR | USE, USERS, ORDERS, TICKETS, STATS |
| MANAGER | USE, CATALOG, PROMOS, PROVIDERS, STATS |
| ADMIN | USE, BROADCAST, SETTINGS, USERS, CATALOG, STATS, BALANCE, PROMOS, ORDERS, PROVIDERS, PAYMENTS |
| SUPERADMIN | все биты включая ADMINS, OWN, AUDIT |

### Проверка

- `pytest tests/test_rbac_tz08.py tests/test_role_management.py`

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-17 — ТЗ-07: промокоды и реферал на заказах

**Ветка:** смержено в `main` (PR #12)

### Сделали

- Миграция `c7d8e9f0a1b2`: `min_order_cents`, `max_uses_per_user`, `promo_code_usages.order_id`, снят `uq_promo_usage_per_user`, unique `referral_earnings.order_id`.
- `promo_rule_error` / `record_promo_usage` / `count_promo_usages_for_user`; повторная проверка лимитов под lock промо.
- Корзина и redeem через `record_promo_usage`; buy_item — usage с `order_id` после создания заказа (ТЗ-06).
- Реферал: `credit_referral_for_order` / `reverse_referral_for_order` на `Order.COMPLETED` / `REFUNDED`; убрано с top-up в `process_payment_with_referral`.
- i18n: тексты «с покупок», не «с пополнений»; SQLAdmin поля промо; тесты `tests/test_promo_referral_tz07.py`.

### Обсуждали

- Параллельный race last-use промо на SQLite in-memory не сериализует `FOR UPDATE` — отдельный skipped-тест; на Postgres ожидается один победитель.

### Отвергли

- *Реферал с пополнения* — *причина:* ТЗ-07, начисление только с завершённого заказа.
- *Ранний increment промо в buy_item (как до ТЗ-06 в main)* — *причина:* usage должен идти с `order_id` после `begin_paid_order`.

### Проверка

- `pytest tests/test_promo_referral_tz07.py`
- `pytest` (полный набор)

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-17 — ТЗ-06: checkout и fulfillment (заказ, баланс, STOCK/API)

**Ветка:** `cursor/fulfillment-worker-tz06-03eb` → `main`

### Сделали

- `bot/misc/services/fulfillment.py`: `begin_paid_order`, `complete_stock_order`, `fulfill_processing_order`, auto-refund `FAILED`→`REFUNDED`, gift → `BoughtGoods.buyer_id` получателя.
- `buy_item_transaction`: заказ + списание; STOCK завершается в транзакции (`COMPLETED`); API → `PROCESSING` + фоновый `fulfill_processing_order_by_id` (без долгого await в handler).
- `select_primary_link_for_session` в `bot/providers/links.py`.
- Тесты `tests/test_fulfillment_tz06.py`; `_checkout_lock` для SQLite StaticPool при конкурентных покупках.

### Обсуждали

- **Корзина:** одна строка = один `Order` — в этом PR пока только `buy_item`; `checkout_cart_transaction` остаётся на legacy-пути (без Order), без регрессии STOCK.
- Реферал на `COMPLETED` — ТЗ-07; retry/backoff воркера — ТЗ-12.

### Отвергли

- *Синхронный await Wizard в handler* — *причина:* ТЗ-06/12; API через task после commit.

### Проверка

- `pytest tests/test_fulfillment_tz06.py`
- `pytest` (полный набор; известный fail `test_concurrent_purchases_do_not_overdraw` на SQLite без lock — смягчён lock для buy_item).

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-16 — ТЗ-05: поставщики цифровых товаров (Wizard, fake, links)

**Ветка:** `cursor/fulfillment-providers-tz05-03eb` → `main`

### Сделали

- Пакет `bot/providers/`: протокол `DigitalGoodsProvider`, DTO, ошибки `ProviderRetryableError` / `ProviderFatalError`, маппинг `result_mapping` → ключ выдачи.
- Адаптеры `FakeProvider` (success / timeout / fatal / идемпотентность по ключу) и `WizardProvider` (REST: `GET /v1/products/{id}`, `POST /v1/orders` с `Idempotency-Key`, `GET /v1/orders/{id}`, cancel).
- Реестр `build_provider(code, config_json)`; сервис `create_external_order` — один вызов create, повтор по уже сохранённому `provider_external_order_id` + `fulfillment_payload` без второго HTTP.
- Модели `FulfillmentProvider`, `GoodsProviderLink`; миграция `b5c6d7e8f9a0_fulfillment_providers_tz05.py` (сид `wizard` / `fake`; FK `orders.provider_id` → `fulfillment_providers`).
- `select_primary_link`, `validate_provider_link` (fake / skip_catalog_validation / get_product).
- SQLAdmin: `FulfillmentProviderAdmin`, `GoodsProviderLinkAdmin`.
- Тесты `tests/test_providers_tz05.py`; сид в `tests/conftest` через `fulfillment_seed`.

### Обсуждали

- Публичной доки Wizard в репо нет — зафиксирован условный `base_url` `https://api.wizard.example`, поля ответа `id`, `status`, `delivery.value` (переопределяются `result_mapping` на link/provider).
- Полный retry-loop и вызов `create_external_order` из воркера — **ТЗ-06** / **ТЗ-12**; здесь один HTTP-запрос и классификация ошибок.
- Платёжный `Payments.provider` не трогали — fulfillment отдельно от Platega (ТЗ-04).

### Отвергли

- *Повторный create при ретрае через новый in-memory Fake без состояния* — *причина:* на ретрае возвращаем заказ из полей `Order`, если payload уже записан; иначе — `get_order_status` (для stateful провайдеров).

### Проверка

- `pytest tests/test_providers_tz05.py` — 7 passed.
- `pytest` — 1000 passed; 1 failed — прежний `test_concurrent_purchases_do_not_overdraw` (SQLite).
- Handlers: нет импортов из `bot/providers`.

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-16 — ТЗ-04: платежи, инструменты, Platega

**Ветка:** `cursor/payments-platega-tz04-03eb` → `main` (смержено в `main`, PR #8)

### Сделали

- Модели `PaymentGateway`, `PaymentInstrument`; `Payments.internal_uuid`.
- Миграция `a4b5c6d7e8f9` + сид «Карта / МИР» → Platega (ключи из env).
- `bot/payments/`: `process_payment_topup` (без реферала), адаптер Platega (`create_payment`, `fetch_status`, webhook headers), `create_topup_via_instrument`, список инструментов из БД.
- Webhook `POST /webhooks/platega` на Starlette (рядом с админкой).
- Handlers: клавиатура методов из БД (`pay_inst_{code}`), ветка Platega + проверка оплаты; CryptoPay manual check → `process_payment_topup`.
- Recovery: pending `platega` опрашивается `fetch_status`.
- SQLAdmin: gateways/instruments; тесты `tests/test_platega_payments.py`.

### Обсуждали

- Stars/Telegram fiat остаются через gateway-код в handler (инструменты в БД, логика прежняя).
- Heleket — gateway disabled, без API в v1.

### Отвергли

- *Реферал с пополнения в ТЗ-04* — *причина:* `process_payment_topup` без referral; реферал с заказа — ТЗ-07.

### Проверка

- `pytest tests/test_platega_payments.py`
- `alembic upgrade head`; env: `PLATEGA_MERCHANT_ID`, `PLATEGA_SECRET`; callback URL в ЛК Platega → `https://<host>/webhooks/platega`

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-16 — ТЗ-03: каталог и склад (fulfillment, резерв, gift)

**Ветка:** `cursor/catalog-stock-tz03-03eb` → `main`

### Сделали

- Пакет `bot/catalog/`: `FulfillmentType`, статусы `StockUnitStatus`, `consume_stock_units`, `reserve_stock_units`, `release_stock_reservations`, проверка `gift_not_allowed`.
- Модели: `Goods.fulfillment_type`, `Goods.allows_gift`; `ItemValues.status`, `ItemValues.reserved_order_id` (FK на `orders`).
- Миграция `f3a4b5c6d7e8_catalog_stock_tz03.py`.
- Покупка и корзина используют `consume_stock_units` (атомарный delete с `status=AVAILABLE`; на Postgres — `SKIP LOCKED` при выборе).
- При переходе заказа в `EXPIRED`/`FAILED` — `release_stock_reservations`.
- Остаток в витрине считает только AVAILABLE (+ infinity).
- Тесты `tests/test_catalog_stock.py` по критериям ТЗ-03.
- SQLAdmin: колонки fulfillment / gift / status.

### Обсуждали

- Резерв до оплаты по TTL заказа `CREATED`: API `reserve_stock_units` готов; `buy_item_transaction` по-прежнему мгновенное списание со склада (без заказа) — полный order-flow в ТЗ-06.
- Подарок: только серверная проверка `gift_recipient_telegram_id` + `allows_gift`; UI — ТЗ-11.

### Отвергли

- *Явный статус SOLD с хранением строки* — *причина:* сохранили прежнее удаление finite-ключа при продаже; RESERVED только для TTL-резерва.

### Проверка

- `pytest tests/test_catalog_stock.py` — все зелёные.
- `pytest` — 993 passed; 1 failed — прежний `test_concurrent_purchases_do_not_overdraw` на SQLite (гонка баланса без `FOR UPDATE`).

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-16 — PR #5: окружение Cloud Agent (Python 3.11, Postgres, Redis)

**Ветка:** `cursor/setup-dev-environment-e567` → `main`  
**PR:** https://github.com/lexa97/telegram-shop/pull/5

### Сделали

- `.cursor/Dockerfile` — Ubuntu 24.04 + Python 3.11 (deadsnakes PPA), PostgreSQL 16, Redis, build-инструменты; venv на `/opt/venv`, добавлен в `PATH`.
- `.cursor/install.sh` — установка `requirements.txt` в venv + генерация dev-`.env` (привязан к встроенным Postgres/Redis); идемпотентно.
- `.cursor/start.sh` — `initdb`+запуск PostgreSQL и Redis под пользователем `ubuntu` (без root), создание роли/БД, `alembic upgrade head`; идемпотентно.
- `.cursor/environment.json` — build (Dockerfile) + install + start; терминал `bot` (`python run.py`); проброс порта 9090 (админка). Конфигурация **repo-managed** — действует после мержа без «Save».

### Обсуждали

- Роль Postgres создаётся как **SUPERUSER**: приложение выставляет `lc_messages` (SUSET-параметр) в `connect_args` (`bot/database/main.py`); официальный postgres-образ делает `POSTGRES_USER` суперпользователем — воспроизвели это, иначе `permission denied to set parameter "lc_messages"`.
- Секреты `TOKEN`/`OWNER_ID` — личные секреты разработчика; `load_dotenv` не перекрывает уже заданные переменные окружения, поэтому реальные секреты из платформы переопределяют плейсхолдеры из dev-`.env`.
- Логи покупок: нажатие «купить» пишется middleware как `critical_action` (`callback=buy_item`); успешная покупка — `action=purchase`; обычные отказы (нет денег/стока) в аудит не пишутся (только `purchase_error` на непредвиденных и `suspicious_item_name`).

### Отвергли

- *Snapshot-based окружение как источник истины* — *причина:* repo-managed `.cursor/environment.json` воспроизводимее и версионируется с кодом (снапшот использован только для build-теста install/start).
- *Править код приложения/тестов ради падающего `test_concurrent_purchases_do_not_overdraw`* — *причина:* это ограничение in-memory SQLite (нет `SELECT ... FOR UPDATE`), не баг окружения; реальный Postgres блокировку обеспечивает.

### Проверка

- `bash .cursor/install.sh && bash .cursor/start.sh` (оба идемпотентны, прогнаны дважды).
- `pytest` → **985 passed, 1 failed** (ожидаемый SQLite row-lock).
- Веб-админка `http://127.0.0.1:9090/admin` (логин/пароль `admin`/`admin`, loopback), `/health → {"status":"healthy"}`, `/admin/ → 302`.
- Живой бот: `python run.py` → `@dev89289bot`, активный long-polling (конкурентный `getUpdates` → `409 Conflict`).
- Draft-build `bld-20260916-143ef07d…` **SUCCEEDED**; свежий Cloud Agent из билда прошёл start.sh, миграции, тесты, `/health`.

### Заметки для агентов

- Запуск живого бота требует секретов `TOKEN` (от @BotFather) и `OWNER_ID` — добавляются в раздел **Secrets**.
- Runtime-логи `logs/bot.log`, `logs/audit.log` — в `.gitignore` (`*.log`) и эфемерны для VM; для передачи фактов будущим агентам используем этот журнал (`docs/MEMORY.md`), а не файлы логов.

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-15 — ТЗ-02: домен заказов (жизненный цикл, snapshot)

**Ветка:** `cursor/orders-domain-54d7` → `main`  
**PR:** https://github.com/lexa97/telegram-shop/pull/3 (смержен в `main`)

### Сделали

- Модели `Order`, `OrderStatusHistory`; статусы `CREATED`…`REFUNDED`, суммы в **копейках** (`BIGINT`).
- Сервис переходов (`bot/database/methods/orders.py`): матрица переходов, snapshot при создании, `profit` при `COMPLETED`, TTL-хелпер `expire_created_if_due`, идемпотентный ручной refund на баланс, запрет user-cancel для оплаченных.
- `BoughtGoods.order_id` (nullable FK); Alembic `e9f0a1b2c3d4` (после `a9b0c1d2e3f4`).
- Тесты `tests/test_orders.py`; refund и баланс — копейки через `bot/money.py`.

### Обсуждали

- Покупка через `buy_item_transaction` пока **без** привязки к `Order` — сделает ТЗ-06 (fulfillment).

### Отвергли

- *Менять flow покупки в этом PR* — *причина:* scope ТЗ-02 только модель и сервис статусов.
- *Дублирующий `bot/database/money.py`* — *причина:* единый модуль `bot/money.py` с main.

### Проверка

- `pytest tests/test_orders.py`
- `alembic upgrade head` (таблицы `orders`, `order_status_history`).

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-15 — PR: ТЗ-01 деньги в копейках (BIGINT)

**Ветка:** `cursor/money-kopecks-eee5` → `main`  
**PR:** https://github.com/lexa97/telegram-shop/pull/6

### Сделали

- Модуль `bot/money.py`: `rub_to_cents`, `cents_to_display`, форматирование для UI и CSV.
- Alembic `a9b0c1d2e3f4`: денежные колонки → `BIGINT` копеек, промо `fixed`/`balance` ×100, `CHECK balance >= 0`.
- Модели, pricing, transactions, платежи, админка, корзина, экспорт CSV — единый контракт копеек в БД, рубли в UI.
- Тесты и factories переведены; добавлен `tests/test_money.py`.
- Merge с `main` (ТЗ-02): единый контракт — **рубли на границе handlers**, `rub_to_cents` внутри `create_item` / `replace_item_stock_and_meta` (не дублировать в handlers).

### Обсуждали

- Фабрики тестов принимают суммы в **рублях** и конвертируют в копейки — меньше шума в тестах.
- `sale_percent` остаётся `Numeric` (процент, не деньги).

### Отвергли

- *ORM-тип `Money`* — *причина:* по ТЗ достаточно `BigInteger` + хелперы.
- *Двойная конвертация в `update_item` из handler и из метода* — конвертация на границе `update_item` / `create_item`.

### Проверка

- `python3 -m pytest -q` (966+ тестов, включая `tests/test_orders.py`).
- Исправление UX: карточка товара и корзина оба через `format_cents_for_ui`; `create_item` / `replace_item_stock_and_meta` принимают **рубли** и конвертируют внутри.
- Профиль пользователя (`profile`): баланс и сумма пополнений через `format_cents_for_ui`.
- SQLAdmin `Users`: баланс в списке/форме в рублях, при сохранении `rub_to_cents`.
- Товары с ошибочной ценой после миграции — пересохранить цену в админке.
- Миграция: `alembic upgrade head` на Postgres после деплоя.

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh`.

---

## 2026-09-15 — Декомпозиция ТЗ Telegram-магазина цифровых товаров

**Ветка:** `cursor/tz-subagent-docs-fdff` → `main`  
**PR:** https://github.com/lexa97/telegram-shop/pull/2

### Сделали

- Разобрали исходное ТЗ заказчика и текущий код (`Goods`/`ItemValues`, баланс `Numeric`, платежи CryptoPay/Stars/Telegram, промо, реферал с **пополнения**, SQLAdmin, роли USER/ADMIN/OWNER).
- Записали пакет заданий для субагентов в `docs/tz/` (индекс, gap-analysis, ТЗ-01…13). Код магазина не менялся.

### Обсуждали

- Корзину платформы сохраняем, хотя краткое ТЗ описывает покупку «одного товара».
- Реферал по ТЗ — с завершённого **заказа**, не с top-up.
- Деньги — копейки `BIGINT`; роли ТЗ мапятся на существующие permission bits.
- Worker остаётся в том же asyncio-процессе, без обязательного Celery.

### Отвергли

- *Писать код в этом PR* — *причина:* задача была только декомпозиция и постановка.
- *Вывод средств с баланса* — *причина:* явное «не в v1» исходного ТЗ.
- *Mini App / отдельное приложение* — *причина:* вне ТЗ.

### Проверка

- Читать с `docs/tz/README.md`; исходник `docs/tz/00-source-brief.md`.

### Graphify

- После merge: код не менялся, полный refresh не обязателен.

---

## 2026-09-15 — PR: подготовка Graphify + skill pr-memory-graphify

**Ветка:** `cursor/graphiti-memory-setup-3d1e` → `main`  
**PR:** https://github.com/lexa97/telegram-shop/pull/1

### Сделали

- Локальный **Graphify** (`graphify-out/`, `devtools/graphify/`).
- Журнал **MEMORY.md** и skill **`/pr-memory-graphify`**: память при готовности PR, Graphify после merge.
- Скрипт `devtools/graphify/refresh-after-merge.sh`.

### Обсуждали

- Graphiti (Neo4j/OpenAI) vs **Graphify** — нужен локальный граф без API.

### Отвергли

- *Graphiti + Neo4j + OpenAI* — *причина:* пользователю нужен локальный **graphify**, не Zep Graphiti.

### Проверка

- `graphify update .` и `graphify cluster-only . --no-label` на репозитории.
- Skill: `.cursor/skills/pr-memory-graphify/SKILL.md`.

### Graphify

- После merge PR #1: `git checkout main && git pull && ./devtools/graphify/refresh-after-merge.sh`, коммит `graphify-out/`.

---

## 2026-09-15 — Подготовка окружения

### Контекст

Репозиторий: **Telegram Shop Bot** — бот для продажи цифровых товаров (каталог, корзина, оплаты, админка в чате и веб).

### Что сделали

- Подключён **Graphify** (`graphifyy`): граф в `graphify-out/`, скрипт `devtools/graphify/build-graph.sh`, правила Cursor `graphify.mdc` + `project-memory.mdc`.
- Убрана ошибочная заготовка под Graphiti (Neo4j/OpenAI) — не нужна для нашего сценария.

### Стек (кратко)

| Слой | Технологии |
|------|------------|
| Бот | Python 3.11+, aiogram 3.22 |
| БД | PostgreSQL 16, SQLAlchemy 2.0 async, Alembic |
| Кэш / FSM | Redis 7 (опционально) |
| Админка | SQLAdmin, Starlette, uvicorn (`/admin`, `/health`, `/metrics`) |
| Контейнеры | Docker Compose (`db`, `redis`, `bot`) |

### Структура кода

```
run.py                 → точка входа, asyncio.run(start_bot)
bot/main.py            → жизненный цикл: Dispatcher, middleware, фоновые задачи, uvicorn
bot/handlers/          → user (магазин, корзина, оплаты) + admin (CRUD, рассылки)
bot/database/          → модели, CRUD, транзакции, аудит
bot/misc/services/     → платежи, recovery, cleanup, broadcast
bot/web/               → SQLAdmin + export
bot/middleware/        → rate limit, auth, security
bot/i18n/              → ru/en строки
migrations/            → Alembic
tests/                 → pytest (широкое покрытие handlers и DB)
```

### Архитектура (суть)

- **Один процесс, один event loop**: бот, веб-панель и воркеры — без отдельного брокера.
- Middleware (снаружи внутрь): RateLimit → Analytics → Auth → Security → роутеры.
- Redis выключен (`REDIS_ENABLED=0`) → in-memory FSM, без shared cache.

### Как запустить (основное приложение)

**Docker (рекомендуется):**

```bash
cp .env.example .env   # TOKEN, OWNER_ID, POSTGRES_*
docker compose up -d --build
# Админка: http://localhost:9090/admin
```

**Локально:**

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python run.py
```

### Graphify (граф по коду, локально)

```bash
uv tool install graphifyy   # или pipx
graphify update .
graphify cluster-only . --no-label
graphify query "payment handlers" --graph graphify-out/graph.json
```

Подробнее: `devtools/graphify/README.md`. Интерактив: `graphify-out/graph.html`.

### Открытые вопросы

- [x] Какие доработки продукта в приоритете после подготовки? → пакет `docs/tz/` (деньги → заказы → склад/платежи/провайдеры → fulfillment).
- [ ] Нужен ли MCP `python -m graphify.serve graphify-out/graph.json` в Cursor?

---

## Шаблон новой записи (PR ready)

```markdown
## YYYY-MM-DD — PR #N: Краткий заголовок

**Ветка:** `feature/...` → `main`  
**PR:** ссылка

### Сделали
- …

### Обсуждали
- …

### Отвергли
- *Идея:* … — *причина:* …

### Проверка
- …

### Graphify
- После merge: refresh на main (PR #N).
```
