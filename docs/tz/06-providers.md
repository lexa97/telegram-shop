# ТЗ-05 — Абстракция поставщиков цифровых товаров и Wizard

**Исполнитель:** субагент «integrations / providers».  
**Исходное ТЗ:** §3.2, §4, §21.8–10.  
**Зависимости:** ТЗ-01, ТЗ-02 (внешний ID заказа).  
**Блокирует:** ТЗ-06 API-ветка.

## Цель

Поставщики **не** протекают в модель товара как хардкод и **не** вызываются из Telegram-handlers. Единый интерфейс + адаптер **Wizard** (или эквивалент «первый поставщик») + fake-провайдер для тестов.

## Контекст кода

Поставщиков цифровых товаров нет. Слово `provider` занято платежами (`Payments.provider`). **Не переиспользовать** это поле для Wizard. Имена: `fulfillment_provider` / пакет `bot/providers/`.

## Задача

1. Протокол (async):

```python
class DigitalGoodsProvider(Protocol):
    async def get_product(self, external_product_id: str) -> ProviderProduct: ...
    async def create_order(self, request: ProviderOrderRequest) -> ProviderOrder: ...
    async def get_order_status(self, external_order_id: str) -> ProviderOrder: ...
    async def cancel_order(self, external_order_id: str) -> None: ...
```

2. Реестр: код поставщика → класс; конфиг (base URL, key, timeout, retry) из БД `FulfillmentProvider`.
3. Связь товар ↔ поставщики: `GoodsProviderLink`: `goods_id`, `provider_id`, `external_product_id`, `cost_cents`, `request_params` JSON, `result_mapping` JSON, timeout/retry, `delivery_template`, `priority`, `enabled`.
4. Один товар — несколько ссылок; выбор: первый enabled по priority (fallback — ТЗ-06).
5. Адаптер **WizardProvider** по публичной/выданной API (агент фиксирует URL и поля в MEMORY). Если ключей нет — полный клиент + кассеты mock.
6. `FakeProvider` для pytest: success / timeout / permanent fail / duplicate create.
7. Идемпотентность `create_order`: передавать `idempotency_key=order.id`; повтор не создаёт второй внешний заказ. Сохранять `provider_external_order_id` на `Order`.
8. Никаких `import Wizard` из `bot/handlers`.

## Направление

- Пакет `bot/providers/` + модели в `bot/database/models`.
- Retry/timeout — настройки на link или provider; сам retry loop — ТЗ-12, здесь клиент с одним запросом + классификация ошибки (retryable vs fatal).
- Маппинг результата: из JSON ответа достать поле выдачи (ключ) по `result_mapping`.

## Вне скоупа

Списание баланса, UI админки форм (модели достаточны для SQLAdmin в ТЗ-10).

## Критерии приёмки

- [ ] Новый поставщик = новый класс + строка реестра, без правок shop handlers.
- [ ] Wizard (или mock совместимый) `create_order` + `get_order_status` покрыты тестами.
- [ ] Повтор `create_order` с тем же idempotency key не вызывает второй paid-заказ на стороне fake.
- [ ] Timeout классифицируется как retryable; 4xx «товар кончился» — fatal.
- [ ] `get_product` используется хотя бы для валидации link в админ-сервисе (можно skip если API не отдаёт каталог — задокументировать).
- [ ] Секреты не попадают в `Order.fulfillment_payload` целиком как raw HTTP dump с Authorization.
