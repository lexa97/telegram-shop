from decimal import Decimal

from bot.money import rub_to_cents
from bot.web.admin import GoodsAdmin, _apply_rubles_field_to_cents


class TestWebAdminMoneyHelpers:

    def test_apply_rubles_field_to_cents(self):
        data = {"price": Decimal("199.99")}
        _apply_rubles_field_to_cents(data, "price")
        assert data["price"] == rub_to_cents("199.99")

    async def test_goods_admin_on_model_change(self):
        data = {"price": "1000"}
        await GoodsAdmin().on_model_change(data, None, True, None)
        assert data["price"] == rub_to_cents("1000")
