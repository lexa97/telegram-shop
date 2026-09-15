from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from bot.money import rub_to_cents


def _get(goods: Any, key: str):
    """Read a field from either an ORM object or a plain dict."""
    if isinstance(goods, dict):
        return goods.get(key)
    return getattr(goods, key, None)


def coerce_sale_until(value: Any) -> datetime | None:
    """Normalize a sale_until value to a timezone-aware datetime (or None).

    Product dicts read from the Redis cache are JSON-serialized (datetime ->
    ISO string via default=str), so this accepts either a datetime or a string.
    Naive datetimes are treated as UTC.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def apply_promo_discount(
        base_price_cents: int, discount_type: str, discount_value: Any, quantity: int = 1
) -> int:
    """Return the discounted line total in kopecks for ``quantity`` units, clamped to >= 0.

    - ``percent``: percentage off each unit; percent clamped to [0, 100].
    - ``fixed``: flat kopecks off the whole line once (not per unit).

    Balance-type promos credit the balance directly and never reach here.
    """
    base = int(base_price_cents)
    qty = max(int(quantity), 0)
    line = base * qty
    if discount_type == 'percent':
        pct = min(max(int(discount_value), 0), 100)
        line = (line * (100 - pct)) // 100
    else:  # 'fixed'
        off = max(int(discount_value), 0)
        line = max(line - off, 0)
    return line


def effective_price(goods: Any, now: datetime | None = None) -> tuple[int, bool, int]:
    """Return (final_price_cents, on_sale, original_price_cents) for a product.

    'goods' may be an ORM 'Goods' instance or a dict with 'price',
    'sale_percent' and 'sale_until' keys. The sale applies only while
    'sale_until' is in the future and 'sale_percent' is a positive percent.
    """
    original = int(_get(goods, 'price'))

    sale_percent = _get(goods, 'sale_percent')
    sale_until = coerce_sale_until(_get(goods, 'sale_until'))

    if sale_percent is None or sale_until is None:
        return original, False, original

    now = now or datetime.now(timezone.utc)

    pct = Decimal(str(sale_percent))
    if sale_until <= now or pct <= 0:
        return original, False, original

    pct = min(pct, Decimal(100))
    # Integer math on kopecks: final = original * (100 - pct) / 100
    pct_bp = int((pct * 100).to_integral_value())  # percent in basis points of a percent (20% -> 2000)
    final = (original * (10000 - pct_bp)) // 10000
    if final < 0:
        final = 0
    return final, True, original


def price_cents_from_rub_input(amount: Any) -> int:
    """Parse admin/user ruble input into kopecks."""
    return rub_to_cents(amount)
