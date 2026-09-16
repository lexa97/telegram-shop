"""ТЗ-03: catalog stock, reservation, gift rules."""

import asyncio

import pytest
from sqlalchemy import func, select

from bot.catalog.enums import FulfillmentType, StockUnitStatus
from bot.catalog.stock import (
    StockAllocationError,
    consume_stock_units,
    release_stock_reservations,
    reserve_stock_units,
)
from bot.database.main import Database
from bot.database.methods.orders import create_order_with_snapshot, transition_order
from bot.database.methods.transactions import buy_item_transaction
from bot.database.models import Goods, ItemValues
from bot.database.models.orders import OrderStatus
from decimal import Decimal


@pytest.mark.asyncio
class TestCatalogStockTz03:
    async def test_two_buyers_one_last_key(self, user_factory, item_factory):
        await user_factory(telegram_id=601001, balance=1000)
        await user_factory(telegram_id=601002, balance=1000)
        await item_factory(name="LastKey", price=100, values=[("only-key", False)])

        r1, r2 = await asyncio.gather(
            buy_item_transaction(601001, "LastKey"),
            buy_item_transaction(601002, "LastKey"),
        )
        winners = [r for r in (r1, r2) if r[0]]
        losers = [r for r in (r1, r2) if not r[0]]
        assert len(winners) == 1
        assert len(losers) == 1
        assert losers[0][1] == "out_of_stock"

        from bot.database.models.main import BoughtGoods

        async with Database().session() as s:
            bought = (await s.execute(select(func.count()).select_from(BoughtGoods))).scalar()
            assert bought == 1

    async def test_reserved_unit_blocks_third_buyer(self, user_factory, item_factory, category_factory):
        await category_factory("Cat")
        await user_factory(telegram_id=602001, balance=5000)
        await user_factory(telegram_id=602002, balance=5000)
        await user_factory(telegram_id=602003, balance=5000)
        from bot.database.methods.create import create_item, add_values_to_item

        await create_item("ReserveItem", "d", 10, "Cat")
        await add_values_to_item("ReserveItem", "k1", False)

        async with Database().session() as s:
            goods = (await s.execute(select(Goods).where(Goods.name == "ReserveItem"))).scalar_one()
            order = await create_order_with_snapshot(
                s,
                user_id=602001,
                goods_id=goods.id,
                quantity=1,
                unit_price_rub=Decimal("10"),
            )
            await reserve_stock_units(s, goods, order.id, 1)
            await s.commit()

        ok, msg, _ = await buy_item_transaction(602002, "ReserveItem")
        assert ok is False
        assert msg == "out_of_stock"

        ok3, _, _ = await buy_item_transaction(602003, "ReserveItem")
        assert ok3 is False

    async def test_release_reservation_on_order_expired(self, user_factory, category_factory):
        await category_factory("Cat2")
        await user_factory(telegram_id=603001, balance=5000)
        from bot.database.methods.create import create_item, add_values_to_item

        await create_item("RelItem", "d", 10, "Cat2")
        await add_values_to_item("RelItem", "release-me", False)

        async with Database().session() as s:
            goods = (await s.execute(select(Goods).where(Goods.name == "RelItem"))).scalar_one()
            order = await create_order_with_snapshot(
                s,
                user_id=603001,
                goods_id=goods.id,
                quantity=1,
                unit_price_rub=Decimal("10"),
            )
            await reserve_stock_units(s, goods, order.id, 1)
            await transition_order(s, order, OrderStatus.EXPIRED, actor_id=603001)
            row = (await s.execute(
                select(ItemValues).where(ItemValues.item_id == goods.id)
            )).scalar_one()
            assert row.status == StockUnitStatus.AVAILABLE
            assert row.reserved_order_id is None

        ok, msg, data = await buy_item_transaction(603001, "RelItem")
        assert ok is True
        assert data["value"] == "release-me"

    async def test_bulk_import_creates_available(self, category_factory):
        await category_factory("BulkCat")
        from bot.database.methods.create import create_item, add_values_bulk

        await create_item("Bulk100", "d", 1, "BulkCat")
        keys = [f"key-{i:03d}" for i in range(100)]
        added, skipped_db, skipped_batch, skipped_inv = await add_values_bulk("Bulk100", keys)
        assert added == 100
        assert skipped_db == skipped_batch == skipped_inv == 0

        async with Database().session() as s:
            goods = (await s.execute(select(Goods).where(Goods.name == "Bulk100"))).scalar_one()
            statuses = (await s.execute(
                select(ItemValues.status).where(ItemValues.item_id == goods.id)
            )).scalars().all()
        assert len(statuses) == 100
        assert all(st == StockUnitStatus.AVAILABLE for st in statuses)

        dup_added, dup_db, _, _ = await add_values_bulk("Bulk100", ["key-000", "key-new"])
        assert dup_added == 1
        assert dup_db == 1

    async def test_api_goods_not_issued_from_stock(self, user_factory, category_factory):
        await category_factory("ApiCat")
        await user_factory(telegram_id=604001, balance=5000)
        from bot.database.methods.create import create_item, add_values_to_item

        await create_item(
            "ApiGood", "d", 10, "ApiCat", fulfillment_type=FulfillmentType.API,
        )
        await add_values_to_item("ApiGood", "should-not-matter", False)

        ok, msg, _ = await buy_item_transaction(604001, "ApiGood")
        assert ok is False
        assert msg == "api_fulfillment"

    async def test_gift_not_allowed_when_flag_false(self, user_factory, item_factory):
        await user_factory(telegram_id=605001, balance=5000)
        await item_factory(name="NoGift", price=10, values=[("v", False)])

        ok, msg, _ = await buy_item_transaction(
            605001, "NoGift", gift_recipient_telegram_id=999888777,
        )
        assert ok is False
        assert msg == "gift_not_allowed"

    async def test_consume_stock_raises_for_api(self, category_factory):
        await category_factory("ApiCat2")
        from bot.database.methods.create import create_item

        await create_item("ApiOnly", "d", 1, "ApiCat2", fulfillment_type=FulfillmentType.API)
        async with Database().session() as s:
            goods = (await s.execute(select(Goods).where(Goods.name == "ApiOnly"))).scalar_one()
            with pytest.raises(StockAllocationError) as exc:
                await consume_stock_units(s, goods, 1)
            assert exc.value.code == "api_fulfillment"
