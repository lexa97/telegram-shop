"""ТЗ-12: fulfillment worker, expire CREATED, idempotent concurrent fulfill."""

import asyncio
import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.catalog.enums import FulfillmentType, StockUnitStatus
from bot.database import Database
from bot.database.methods.create import create_item, add_values_to_item
from bot.database.methods.orders import (
    create_order_with_snapshot,
    expire_due_created_orders,
    transition_order,
)
from bot.database.methods.transactions import buy_item_transaction
from bot.database.models.fulfillment_providers import FulfillmentProvider, GoodsProviderLink
from bot.database.models.main import Goods, ItemValues, User
from bot.database.models.orders import Order, OrderStatus
from bot.misc.services.fulfillment import fulfill_processing_order_by_id
from bot.misc.services.fulfillment_worker import FulfillmentWorker
from bot.money import rub_to_cents


@pytest.mark.asyncio
async def test_worker_expire_created_releases_stock(user_factory, category_factory):
    await category_factory("W12Cat")
    await user_factory(telegram_id=712001, balance=5000)
    await create_item("W12Expire", "d", 10, "W12Cat")
    await add_values_to_item("W12Expire", "ttl-key", False)

    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "W12Expire"))).scalar_one()
        goods_id = goods.id
        order = await create_order_with_snapshot(
            s,
            user_id=712001,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("10"),
            expires_at=past,
        )
        from bot.catalog.stock import reserve_stock_units

        await reserve_stock_units(s, goods, order.id, 1)
        await s.commit()

    async with Database().session() as s:
        n = await expire_due_created_orders(s, limit=10)
        assert n == 1

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.user_id == 712001))).scalar_one()
        assert order.status == OrderStatus.EXPIRED
        row = (await s.execute(select(ItemValues).where(ItemValues.item_id == goods_id))).scalar_one()
        assert row.status == StockUnitStatus.AVAILABLE


@pytest.mark.asyncio
async def test_concurrent_fulfill_single_external_order(user_factory, category_factory):
    await category_factory("W12Api")
    await user_factory(telegram_id=712010, balance=5000)
    await create_item("W12Race", "d", 10, "W12Api", fulfillment_type=FulfillmentType.API)

    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "W12Race"))).scalar_one()
        fake = (
            await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
        ).scalar_one()
        s.add(
            GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake.id,
                external_product_id="race-prod",
                enabled=True,
                priority=1,
            )
        )
        await s.commit()

    ok, _, data = await buy_item_transaction(712010, "W12Race")
    assert ok
    order_id = data["order_id"]

    await asyncio.gather(
        fulfill_processing_order_by_id(order_id),
        fulfill_processing_order_by_id(order_id),
    )

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.status == OrderStatus.COMPLETED
        ext = order.provider_external_order_id
        assert ext

    async with Database().session() as s:
        dup = (
            await s.execute(
                select(Order).where(Order.provider_external_order_id == ext)
            )
        ).scalars().all()
        assert len(dup) == 1


@pytest.mark.asyncio
async def test_max_retries_refund_balance(user_factory, category_factory):
    await category_factory("W12Retry")
    await user_factory(telegram_id=712011, balance=5000)
    await create_item("W12MaxRetry", "d", 10, "W12Retry", fulfillment_type=FulfillmentType.API)

    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "W12MaxRetry"))).scalar_one()
        fake_row = (
            await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
        ).scalar_one()
        fake_row.config_json = '{"mode":"timeout"}'
        s.add(
            GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake_row.id,
                external_product_id="max-retry",
                retry_count=1,
                enabled=True,
                priority=1,
            )
        )
        await s.commit()

    ok, _, data = await buy_item_transaction(712011, "W12MaxRetry")
    assert ok
    tick = await fulfill_processing_order_by_id(data["order_id"])
    assert tick.status == "refunded"

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == data["order_id"]))).scalar_one()
        assert order.status == OrderStatus.REFUNDED
        user = (await s.execute(select(User).where(User.telegram_id == 712011))).scalar_one()
        assert user.balance == rub_to_cents(Decimal("5000"))


@pytest.mark.asyncio
async def test_completed_order_unchanged_by_worker_tick(user_factory, item_factory):
    await user_factory(telegram_id=712020, balance=5000)
    await item_factory(name="W12Done", price=10, values=[("done-key", False)])
    ok, _, data = await buy_item_transaction(712020, "W12Done")
    assert ok

    worker = FulfillmentWorker(bot=None)
    await worker._tick()

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == data["order_id"]))).scalar_one()
        assert order.status == OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_timeout_then_success_via_worker_poll(user_factory, category_factory):
    await category_factory("W12Poll")
    await user_factory(telegram_id=712030, balance=5000)
    await create_item("W12Poll", "d", 10, "W12Poll", fulfillment_type=FulfillmentType.API)

    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "W12Poll"))).scalar_one()
        fake_row = (
            await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
        ).scalar_one()
        fake_row.config_json = '{"mode":"timeout"}'
        s.add(
            GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake_row.id,
                external_product_id="poll-prod",
                retry_count=5,
                enabled=True,
                priority=1,
            )
        )
        await s.commit()

    ok, _, data = await buy_item_transaction(712030, "W12Poll")
    assert ok
    order_id = data["order_id"]

    tick1 = await fulfill_processing_order_by_id(order_id)
    assert tick1.status == "retry"

    async with Database().session() as s:
        fake_row = (
            await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
        ).scalar_one()
        fake_row.config_json = '{"mode":"success"}'

    tick2 = await fulfill_processing_order_by_id(order_id)
    assert tick2.status == "completed"

    async with Database().session() as s:
        order = (
            await s.execute(
                select(Order).where(Order.id == order_id).options(selectinload(Order.bought_goods))
            )
        ).scalar_one()
        assert order.status == OrderStatus.COMPLETED
        assert order.provider_external_order_id
        tick3 = await fulfill_processing_order_by_id(order_id)
    assert tick3.status == "noop"
