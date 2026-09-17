# Wizard Bot API (fulfillment)

Документация: [https://api.wizard-bot.com/docs/](https://api.wizard-bot.com/docs/)

## Настройка в SQLAdmin

**Fulfillment Provider** с `code = wizard`, `config_json`:

```json
{
  "base_url": "https://api.wizard-bot.com/v1",
  "api_key": "ваш-ключ-из-telegram-бота-wizard",
  "timeout_seconds": 30
}
```

Ключ передаётся в заголовке **`X-API-KEY`** (не Bearer).

## Goods Provider Link

- **`external_product_id`**: `stars` или `premium` (категория заказа Wizard).
- **`request_params`** (обязательно для создания заказа):

```json
{
  "recipient": "username_получателя_без_собаки"
}
```

- **`quantity`** на заказе магазина:
  - для `stars` — число звёзд (50–1 000 000);
  - для `premium` — только `3`, `6` или `12` (месяцы).

Списание идёт с **баланса аккаунта Wizard**, не с баланса покупателя в вашем боте (у вас списывается внутренний баланс, Wizard — отдельный кошелёк).

## Жизненный цикл

`in_queue` → `pending` → `processing` → `success` | `failed`

Воркер опрашивает `GET /orders/get/{id}` до `success`. В выдачу покупателю попадает строка вида `stars:100→@username`.

## Ограничения

- Отмена заказа в API Wizard не предусмотрена (`cancel_order` → fatal).
- Каталога товаров нет: `get_product` проверяет только категорию `stars`/`premium`.
