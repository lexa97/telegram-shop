"""ТЗ-11: UX бота — заказы, подарки, подтверждение покупки."""

import pytest

from bot.database.methods.lazy_queries import query_user_orders
from bot.database.methods.transactions import buy_item_transaction
from bot.database import Database
from bot.database.models.main import Goods
from sqlalchemy import select


@pytest.mark.asyncio
async def test_gift_recipient_must_exist(user_factory, item_factory):
    await user_factory(telegram_id=880101, balance=5000)
    await item_factory(name="GiftUx", price=10, values=[("k", False)])
    async with Database().session() as s:
        g = (await s.execute(select(Goods).where(Goods.name == "GiftUx"))).scalar_one()
        g.allows_gift = True
        await s.commit()

    ok, msg, _ = await buy_item_transaction(880101, "GiftUx", gift_recipient_telegram_id=999888001)
    assert ok is False and msg == "gift_recipient_not_registered"


@pytest.mark.asyncio
async def test_query_user_orders_lists_purchase(user_factory, item_factory):
    await user_factory(telegram_id=880102, balance=5000)
    await item_factory(name="OrdUx", price=10, values=[("k2", False)])
    ok, _, data = await buy_item_transaction(880102, "OrdUx")
    assert ok and data.get("order_id")

    rows = await query_user_orders(880102, limit=5)
    assert any(r["id"] == data["order_id"] and r["status"] == "COMPLETED" for r in rows)
