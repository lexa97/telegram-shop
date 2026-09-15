# ТЗ-12 — Фоновые задачи, идемпотентность, истечение

**Исполнитель:** субагент «workers».  
**Исходное ТЗ:** §17, §18.  
**Зависимости:** ТЗ-02, 04, 05, 06.  
**Блокирует:** устойчивость API-покупок и pending Platega.

## Цель

Один процесс как сейчас (`bot/main.py`: Recovery + Cleanup), плюс циклы:

- PROCESSING заказы: poll/retry Provider;
- retryable ошибки по retry policy;
- зависшие PROCESSING старше N;
- CREATED неоплаченные → EXPIRED + снятие резерва склада;
- проверка статусов внешних заказов и платежей Platega;
- **не** блокировать polling Telegram.

## Контекст кода

`RecoveryManager` — pending CryptoPay. `CleanupManager`. Кэш `CacheScheduler`. Всё на asyncio tasks.

Отдельный Celery **не обязателен** (ТЗ: Redis при необходимости). Предпочтение: расширить Recovery/добавить `FulfillmentWorker` в том же event loop. Если появится Redis lock — только чтобы два инстанса не двойнили (unique в БД всё равно обязателен).

## Задача

1. Воркер заказов: выбрать `PROCESSING` `FOR UPDATE SKIP LOCKED`, вызвать fulfill idempotent.
2. Backoff из настроек link/provider; max attempts → FAILED/REFUNDED через сервис ТЗ-06.
3. Expire CREATED.
4. Platega pending: fetch_status (вместе с ТЗ-04).
5. Метрики/логи без PII ключей товаров.
6. Повторная выдача: если COMPLETED — не слать ключ второй раз (флаг `delivery_notified_at`).

## Направление

- Интервалы как у Recovery (секунды, env).
- Транзакции короткие: HTTP вне открытой DB-транзакции, затем коротко обновить статус.

## Вне скоупа

Новые платёжные шлюзы. Переписывание broadcast.

## Критерии приёмки

- [ ] FakeProvider timeout: N retry, затем успех — один внешний заказ.
- [ ] После max retry деньги на балансе, заказ не PROCESSING.
- [ ] Два воркера (два concurrent task) на один заказ не делают два create_order.
- [ ] CREATED с истекшим `expires_at` → EXPIRED, ключ снова AVAILABLE.
- [ ] COMPLETED не переходит никуда воркером.
- [ ] Бот отвечает на callback, пока воркер спит на HTTP (тест с fake sleep опционален; минимум — fulfill вызывается не из handler await цепочки > timeout Telegram).
