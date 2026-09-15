"""Money helpers: all order/payment snapshots use integer kopecks (1 ₽ = 100)."""

from decimal import Decimal, ROUND_HALF_UP


def rub_to_cents(amount: Decimal | int | float | str) -> int:
    """Convert rubles (Decimal or numeric) to integer kopecks."""
    if isinstance(amount, int) and not isinstance(amount, bool):
        # Bare int in legacy code is whole rubles unless already documented as cents.
        return amount * 100
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_rub_decimal(cents: int) -> Decimal:
    """Display helper: kopecks → Decimal rubles with two fractional digits."""
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))
