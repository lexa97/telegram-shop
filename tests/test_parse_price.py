from decimal import Decimal

from bot.handlers.admin._common import parse_price
from bot.money import rub_to_cents


class TestParsePrice:

    def test_whole_rubles(self):
        assert parse_price("100") == "100"

    def test_kopecks(self):
        assert parse_price("199.99") == "199.99"
        assert parse_price("10,50") == "10.50"

    def test_rejects_invalid(self):
        assert parse_price("") is None
        assert parse_price("abc") is None
        assert parse_price("0") is None
        assert parse_price("-10") is None
        assert parse_price("1.234") is None

    def test_converts_to_cents(self):
        assert rub_to_cents(parse_price("29.99")) == 2999
