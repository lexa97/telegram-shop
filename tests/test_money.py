import pytest

from bot.money import rub_to_cents, cents_to_display, cents_to_float_rub
from bot.database.methods.pricing import apply_promo_discount, effective_price
from bot.database.methods.transactions import _split_amount as tx_split


@pytest.mark.parametrize(
    "rub, cents",
    [
        (0, 0),
        (1, 100),
        ("10.50", 1050),
        ("299", 29900),
    ],
)
def test_rub_to_cents(rub, cents):
    assert rub_to_cents(rub) == cents


def test_cents_to_display():
    assert cents_to_display(29900) == "299"
    assert cents_to_display(1050) == "10.50"


def test_split_amount_sums():
    parts = tx_split(1050, 3)
    assert parts == [350, 350, 350]
    assert sum(parts) == 1050


def test_apply_promo_fixed_cents():
    assert apply_promo_discount(10000, "fixed", 500, 1) == 9500


def test_effective_sale_cents():
    final, on_sale, original = effective_price(
        {"price": 10000, "sale_percent": 20, "sale_until": "2099-01-01T00:00:00+00:00"}
    )
    assert on_sale is True
    assert original == 10000
    assert final == 8000
