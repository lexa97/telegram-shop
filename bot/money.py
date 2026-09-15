"""Money helpers: all persisted monetary amounts are integer kopecks (1 ₽ = 100).

Percent fields (sale_percent, promo discount_type=percent) are not money.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

MoneyInput = Union[int, Decimal, str, float]


def rub_to_cents(amount: MoneyInput) -> int:
    """Convert a ruble amount (max 2 decimal places) to kopecks."""
    d = Decimal(str(amount))
    if d.as_tuple().exponent < -2:
        raise ValueError("Amount can have at most 2 decimal places")
    cents = (d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def cents_to_display(cents: int) -> str:
    """Format kopecks as rubles for Telegram/UI (e.g. 29900 -> '299', 1050 -> '10.50')."""
    sign = "-" if cents < 0 else ""
    abs_cents = abs(int(cents))
    rub, kop = divmod(abs_cents, 100)
    if kop == 0:
        return f"{sign}{rub}"
    return f"{sign}{rub}.{kop:02d}"


def cents_to_float_rub(cents: int) -> float:
    """Convert kopecks to a float ruble value for legacy JSON/API payloads."""
    return int(cents) / 100.0


def format_cents_for_ui(cents: int) -> str:
    """Alias for UI strings passed into i18n ``amount`` placeholders."""
    return cents_to_display(cents)


def cents_to_csv_amount(cents: int) -> str:
    """Format kopecks as a fixed two-decimal ruble string for CSV export."""
    sign = "-" if cents < 0 else ""
    abs_cents = abs(int(cents))
    rub, kop = divmod(abs_cents, 100)
    return f"{sign}{rub}.{kop:02d}"
