# ТЗ-06 — Выполнение покупки: баланс, склад, API, выдача

**Исполнитель:** субагент «checkout / fulfillment».  
**Исходное ТЗ:** §5, §6, §10 (авто-refund), §17.  
**Зависимости:** ТЗ-01, 02, 03, 05. Платежи ТЗ-04 не обязательны (оплата с баланса).  
**Блокирует:** ТЗ-11 UX покупки, ТЗ-12 (ставит PROCESSING), ТЗ-07 (COMPLETED).

## Цель

Единый сценарий покупки за внутренний баланс:

1. Выбор товара (и получателя: себя или gift).
2. Создание заказа, проверка баланса, атомарное списание.
3. STOCK: резерв единицы → выдача → COMPLETED.
4. API: PROCESSING → create_order у Provider → результат → выдача → COMPLETED.
5. Фатальный fail API → FAILED → refund на баланс.
6. Retry не покупает у поставщика второй раз.

Бот **не** await'ит долгий HTTP: после списания заказ в PROCESSING, worker (ТЗ-12) добивает; короткое локальное STOCK можно завершить в том же запросе.

## Контекст кода

`buy_item_transaction` / корзина `checkout` в `transactions.py` — база. Нужно разрезать: создание `Order` + списание + fulfill STOCK vs enqueue API.

Корзину сохранить: каждая позиция → заказ(ы) или один заказ с линиями. **Решение:** одна строка корзины = один `Order` (проще snapshot и API). Зафиксировать в MEMORY.

## Задача

1. Заменить/обернуть `buy_item_transaction`:
   - lock user;
   - посчитать total в копейках (sale + promo из ТЗ-07 контракта);
   - недостаточно средств → ошибка без заказа или заказ CREATED без списания (выбрать одно, TTL);
   - списание `balance -= total` с `CHECK >= 0`;
   - STOCK: lock item SKIP LOCKED, выдать, BoughtGoods, COMPLETED;
   - API: PROCESSING, сохранить cost snapshot с выбранного link.
2. Идемпотентный ключ fulfill: `order.id`. Повтор обработки PROCESSING не вызывает второй `create_order` если `provider_external_order_id` уже есть — только poll status.
3. Выдача: сообщение с контентом (ТЗ-11 тексты); сохранение в `order.fulfillment_result` / BoughtGoods.
4. Gift: списание с покупателя, выдача получателю, покупателю без секрета.
5. Авто-refund: FAILED после исчерпания retry → `balance += total`, статус REFUNDED или FAILED+отдельный refund flag. ТЗ: FAILED → Refund → баланс. Предпочтительно конечный `REFUNDED` если деньги вернули, `FAILED` если ещё нет (не должны зависнуть FAILED с удержанными деньгами).
6. Не делать пользовательский cancel после списания.

## Направление

- Вынести оркестратор в `bot/misc/services/fulfillment.py` (имя свободное), handlers тонкие.
- Согласовать промо с ТЗ-07: вызов общего `apply_promo` внутри транзакции заказа.
- Реферал на COMPLETED — вызов сервиса ТЗ-07, не копипастить.

## Вне скоупа

Реализация HTTP Wizard (только вызов протокола). Platega. SQLAdmin.

## Критерии приёмки

- [ ] Успешный STOCK: баланс уменьшен на total_cents, единица SOLD, заказ COMPLETED, контент в BoughtGoods.
- [ ] Два клиента на 1 ключ: один COMPLETED, один ошибка stock, баланс второго не списан (или полностью откат).
- [ ] API success (FakeProvider): COMPLETED, внешний id сохранён, контент выдан.
- [ ] API timeout затем success на retry: один внешний заказ, одно списание.
- [ ] API fatal: REFUNDED, баланс восстановлен, склад не тронут.
- [ ] Повторный worker tick по COMPLETED — no-op, без второй выдачи и без второго реферала.
- [ ] Gift: получатель ≠ плательщик получает value.
- [ ] Существующий cart checkout не регрессирует для STOCK (адаптировать тесты `tests/test_cart_reviews.py` / transactions).
