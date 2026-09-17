# ТЗ-13 — Тесты критической логики, Docker, сдача

**Исполнитель:** субагент «QA / release».  
**Исходное ТЗ:** §20, §21.  
**Зависимости:** все предыдущие ТЗ (зелёный прогон — после merge воркеров и UX).

## Цель

Набор автотестов из §20 и готовый контур запуска: Docker Compose, миграции, README. Моки в CI + [manual-qa.md](manual-qa.md) для staging.

## §20 — автотесты (карта)

| §20 | Сценарий | Тест |
|-----|----------|------|
| 1 | Регистрация `/start` | `tests/test_user_handlers.py::TestStartHandler::test_start_creates_new_user` |
| 1 | Реферальная ссылка | `tests/test_user_handlers.py::TestStartHandler::test_start_with_referral` |
| 2 | Пополнение (Platega мок) | `tests/test_platega_payments.py::TestPlategaGateway::test_webhook_credits_balance_once` |
| 2 | Повторный webhook / idempotency | `tests/test_platega_payments.py::TestPlategaGateway::test_webhook_credits_balance_once` (двойной вызов); `tests/test_transactions.py::TestProcessPaymentWithReferral::test_payment_idempotency` |
| 3 | Покупка STOCK | `tests/test_fulfillment_tz06.py::test_stock_purchase_creates_completed_order` |
| 4 | Конкурентная покупка одного ключа | `tests/test_fulfillment_tz06.py::test_two_buyers_one_key` |
| 5 | Покупка API | `tests/test_fulfillment_tz06.py::test_api_fake_completes_with_delivery` |
| 6–7 | Timeout + retry API | `tests/test_fulfillment_tz06.py::test_api_timeout_then_success_one_external_order` |
| 8–9 | Fatal + auto-refund | `tests/test_fulfillment_tz06.py::test_api_fatal_refunds_balance` |
| 10 | Повторная обработка заказа (worker) | `tests/test_workers_tz12.py::test_concurrent_fulfill_single_external_order` |
| 11 | Промокоды, гонка uses | `tests/test_promo_referral_tz07.py::test_redeem_last_use_race_parallel` |
| 12 | Реферал с заказа | `tests/test_promo_referral_tz07.py::test_referral_on_completed_order` |
| 12 | Нет реферала с top-up | `tests/test_promo_referral_tz07.py::test_topup_no_referral_earnings` |
| 13 | Expire CREATED | `tests/test_workers_tz12.py::test_worker_expire_created_releases_stock` |
| 14 | Роли OPERATOR | `tests/test_rbac_tz08.py::test_builtin_role_masks`, `test_operator_console_hides_roles_and_balance` |
| 15 | Админ refund + audit | `tests/test_rbac_tz08.py::test_order_refund_writes_audit` |

Регрессия привязки: `tests/test_tz13_coverage_map.py` (проверяет, что перечисленные тесты существуют).

## §21 — результат разработки (v1)

| # | Требование | Статус | Где |
|---|------------|--------|-----|
| 1 | Telegram-бот | сделано | `bot/`, `run.py` |
| 2 | Web-панель администратора | сделано | `bot/web/admin.py`, `/admin` |
| 3 | Внутренний баланс | сделано | `users.balance` (копейки) |
| 4 | Пополнение Platega | сделано | `bot/payments/`, webhook `/webhooks/platega` |
| 5 | Каталог цифровых товаров | сделано | handlers + `goods` |
| 6 | STOCK + автовыдача | сделано | `bot/catalog/stock.py`, ТЗ-06 |
| 7 | API + автозакупка | сделано | `bot/providers/`, worker ТЗ-12 |
| 8 | Универсальный Provider API | сделано | `DigitalGoodsProvider`, `bot/providers/` |
| 9 | Wizard (первый поставщик) | сделано | `bot/providers/wizard.py` |
| 10 | Добавление поставщиков | сделано | `fulfillment_providers` + links в админке |
| 11 | Промокоды | сделано | ТЗ-07 |
| 12 | Реферальная система | сделано | начисление с `COMPLETED` заказа |
| 13 | Поддержка | сделано | ТЗ-09 tickets |
| 14 | Статистика и отчёты | сделано | админка, export CSV |
| 15 | RBAC | сделано | ТЗ-08 |
| 16 | Аудит | сделано | `audit_log`, batch buffer |
| 17 | Идемпотентность финансов | сделано | unique payments, FOR UPDATE, тесты |
| 18 | Docker + инструкции | сделано | `docker-compose.yml`, `README.md` |
| 19 | Миграции Alembic | сделано | `migrations/versions/` |
| 20 | Автотесты критической логики | сделано | `tests/`, карта выше |
| — | **Вывод средств с баланса** | **не в v1** | по исходному ТЗ |

## Запуск

```bash
cp .env.example .env   # заполнить TOKEN, OWNER_ID, POSTGRES_*
docker compose up -d --build
# панель: http://localhost:9090/admin , health: http://localhost:9090/health
# Platega webhook (HTTPS): https://<host>/webhooks/platega  (порт панели, не WEBHOOK_PORT)
# Telegram bot webhook (опционально): WEBHOOK_ENABLED=1 → порт 8080, см. README

alembic upgrade head   # чистая БД
pytest                 # без Redis: REDIS_ENABLED=0 в .env тестов/conftest
```

Ручная приёмка: [manual-qa.md](manual-qa.md).

## Критерии приёмки

- [x] `pytest` зелёный локально (`README.md` → Testing).
- [x] Список §20 со ссылками на test-функции (таблица выше).
- [x] `docker compose up` поднимает бота и `/health` (порт 9090).
- [x] `alembic upgrade head` с чистой БД (entrypoint / manual).
- [x] README: Platega webhook, копейки, роли, нет вывода средств.
- [x] §21: таблица результата выше.
