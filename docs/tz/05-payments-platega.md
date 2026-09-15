# ТЗ-04 — Платёжные инструменты, шлюзы и Platega

**Исполнитель:** субагент «платежи».  
**Исходное ТЗ:** §7, §8.  
**Зависимости:** ТЗ-01. Желательно ТЗ-02 не обязателен (пополнение баланса, не заказ товара).  
**Блокирует:** UX пополнения (ТЗ-11), часть админки (ТЗ-10), recovery (ТЗ-12).

## Цель

Пополнение внутреннего баланса. Слой **инструмент** (что выбирает пользователь: карта МИР, СБП, крипта…) отдельно от **шлюза** (Platega, Heleket, CryptoPay…). Настройки в **БД**, управление в админке (сами формы — ТЗ-10, модель и API — здесь). Первый боевой шлюз пополнения по ТЗ — **Platega**.

## Контекст кода

- Выбор метода: `bot/handlers/user/balance_and_payment.py` (callbacks → cryptopay / stars / telegram).
- Создание инвойса: `bot/misc/services/payment.py` (CryptoPay, Stars, fiat invoice).
- Зачисление: `process_payment_with_referral` в `transactions.py`; unique `(provider, external_id)`.
- Recovery pending CryptoPay: `bot/misc/services/recovery.py`.
- Конфиг через `EnvKeys`, не БД.

Текущие шлюзы **не выкидывать**: оформить как gateway-адаптеры рядом с Platega. Реферал с пополнения убрать в ТЗ-07; **здесь** зачисление баланса без реф.бонуса или с флагом `credit_only` — согласовать: предпочтительно `process_payment` без referral, referral вызовет ТЗ-07 с заказа.

## Задача

1. Модели: `PaymentInstrument` (код, название, enabled, sort, currency=RUB), `PaymentGateway` (код `platega`/`cryptopay`/…, credentials/config JSON, enabled), связь many-to-one: инструмент → шлюз.
2. Сид: инструмент «Карта / МИР» → Platega (ключи из env на период миграции, потом БД).
3. Протокол шлюза: `create_payment`, `parse_webhook`, `fetch_status` — **не** в handlers.
4. Адаптер **Platega**: создание платежа, ссылка на оплату, webhook, проверка статуса, сохранение `Payments`.
5. Webhook endpoint FastAPI (рядом с SQLAdmin): подпись/секрет по доке Platega; идемпотентное зачисление.
6. Повтор webhook / повторный статус: баланс +1 раз.
7. Каждый платёж: внутренний UUID + `external_id` шлюза; unique как сейчас.
8. Вынести секреты: в v1 допустим env + запись в gateway.config; не логировать секреты.

## Направление

- Документацию Platega агент обязан сверить с актуальной API (create invoice, webhook events). Если API недоступно в среде — интерфейс + httpx mock в тестах и `NotImplemented` только запрещён: нужен рабочий клиент с запиненными URL.
- Telegram webhook бота не блокировать: HTTP сервер уже крутится с админкой (`bot/main.py` uvicorn).
- Крипта через Heleket — **заглушка шлюза**, не обязательна к полному API в v1, но инструмент можно скрыть `enabled=false`.

## Вне скоупа

Покупка товара, Wizard, смена ролей.

## Критерии приёмки

- [ ] Создание платежа Platega возвращает URL; в `payments` строка `pending`.
- [ ] Успешный webhook: баланс += amount_cents, статус `paid`/`completed`.
- [ ] Повтор того же webhook: баланс не меняется, HTTP 200.
- [ ] Поддельная подпись / без секрета — 4xx, без зачисления.
- [ ] Выключенный инструмент не предлагается API списка методов.
- [ ] Смена шлюза инструмента в БД не требует правки handlers (handlers читают список из БД).
- [ ] Тесты адаптера с httpx mock; тест идемпотентности как `tests/test_payment_service.py`.
- [ ] Recovery: pending Platega опрашивается статусом (расширить RecoveryManager или ТЗ-12).
