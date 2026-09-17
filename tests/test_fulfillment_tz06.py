"""ТЗ-06: checkout orchestration — orders, stock, API, refund."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.catalog.enums import FulfillmentType
from bot.database import Database
from bot.database.methods.create import create_item
from bot.database.methods.orders import create_order_with_snapshot
from bot.database.methods.transactions import buy_item_transaction
from bot.database.models.fulfillment_providers import FulfillmentProvider, GoodsProviderLink
from bot.database.models.main import BoughtGoods, Goods, ItemValues, User
from bot.database.models.orders import DeliveryType, Order, OrderStatus
from bot.misc.services.fulfillment import fulfill_processing_order, fulfill_processing_order_by_id
from bot.money import rub_to_cents
from bot.providers.fake import FakeProvider
from bot.providers.registry import build_provider


@pytest.mark.asyncio
async def test_stock_purchase_creates_completed_order(user_factory, item_factory):
    await user_factory(telegram_id=701001, balance=5000)
    await item_factory(name="StockTz06", price=10, values=[("key-a", False)])

    ok, msg, data = await buy_item_transaction(701001, "StockTz06")
    assert ok and msg == "success"
    assert data["value"] == "key-a"
    assert data.get("order_id")

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == data["order_id"]))).scalar_one()
        assert order.status == OrderStatus.COMPLETED
        assert order.total_cents == rub_to_cents(Decimal("10"))
        user = (await s.execute(select(User).where(User.telegram_id == 701001))).scalar_one()
        assert user.balance == rub_to_cents(Decimal("4990"))


@pytest.mark.asyncio
async def test_two_buyers_one_key(user_factory, item_factory):
    await user_factory(telegram_id=701002, balance=5000)
    await user_factory(telegram_id=701003, balance=5000)
    await item_factory(name="SingleKey", price=10, values=[("only", False)])

    ok1, _, _ = await buy_item_transaction(701002, "SingleKey")
    ok2, msg2, _ = await buy_item_transaction(701003, "SingleKey")
    assert ok1 is True
    assert ok2 is False and msg2 == "out_of_stock"

    async with Database().session() as s:
        loser = (await s.execute(select(User).where(User.telegram_id == 701003))).scalar_one()
        assert loser.balance == rub_to_cents(Decimal("5000"))


@pytest.mark.asyncio
async def test_api_fake_completes_with_delivery(user_factory, category_factory):
    await category_factory("ApiCat6")
    await user_factory(telegram_id=701010, balance=5000)
    await create_item("ApiFake", "d", 10, "ApiCat6", fulfillment_type=FulfillmentType.API)

    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "ApiFake"))).scalar_one()
        fake = (
            await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
        ).scalar_one()
        s.add(
            GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake.id,
                external_product_id="prod-x",
                cost_cents=300,
                enabled=True,
                priority=1,
            )
        )
        await s.commit()

    from bot.database.methods.cache_utils import drain_background_tasks

    ok, msg, data = await buy_item_transaction(701010, "ApiFake")
    assert ok and data["order_id"]
    await drain_background_tasks()
    tick = await fulfill_processing_order_by_id(data["order_id"])
    assert tick.status in ("completed", "noop")

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == data["order_id"]))).scalar_one()
        assert order.status == OrderStatus.COMPLETED
        assert order.provider_external_order_id
        bg = (
            await s.execute(select(BoughtGoods).where(BoughtGoods.order_id == order.id))
        ).scalars().first()
        assert bg and bg.value.startswith("KEY-")


@pytest.mark.asyncio
async def test_api_timeout_then_success_one_external_order(user_factory, category_factory):
    await category_factory("ApiCat7")
    await user_factory(telegram_id=701011, balance=5000)
    await create_item("ApiRetry", "d", 10, "ApiCat7", fulfillment_type=FulfillmentType.API)

    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "ApiRetry"))).scalar_one()
        fake_row = (
            await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
        ).scalar_one()
        fake_row.config_json = '{"mode":"timeout"}'
        s.add(
            GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake_row.id,
                external_product_id="retry-prod",
                enabled=True,
                priority=1,
            )
        )
        await s.commit()

    ok, _, data = await buy_item_transaction(701011, "ApiRetry")
    assert ok
    order_id = data["order_id"]

    async with Database().session() as s:
        tick1 = await fulfill_processing_order(s, order_id)
        assert tick1.status == "retry"

    fake_row = FakeProvider(mode="success")
    fake_row.seed_product("retry-prod")

    async with Database().session() as s:
        order = (
            await s.execute(
                select(Order)
                .where(Order.id == order_id)
                .options(selectinload(Order.goods))
            )
        ).scalar_one()
        link = (
            await s.execute(
                select(GoodsProviderLink).where(GoodsProviderLink.goods_id == order.goods_id)
            )
        ).scalars().first()
        link_provider = (
            await s.execute(
                select(FulfillmentProvider).where(FulfillmentProvider.id == link.provider_id)
            )
        ).scalar_one()
        link_provider.config_json = '{"mode":"success"}'
        tick2 = await fulfill_processing_order(s, order_id)
        assert tick2.status == "completed"

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.status == OrderStatus.COMPLETED
        ext = order.provider_external_order_id
        assert ext

    async with Database().session() as s:
        tick3 = await fulfill_processing_order(s, order_id)
        assert tick3.status == "noop"


@pytest.mark.asyncio
async def test_api_fatal_refunds_balance(user_factory, category_factory):
    await category_factory("ApiCat8")
    await user_factory(telegram_id=701012, balance=5000)
    await create_item("ApiFatal", "d", 10, "ApiCat8", fulfillment_type=FulfillmentType.API)

    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "ApiFatal"))).scalar_one()
        fake_row = (
            await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
        ).scalar_one()
        fake_row.config_json = '{"mode":"fatal"}'
        s.add(
            GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake_row.id,
                external_product_id="f-prod",
                enabled=True,
                priority=1,
            )
        )
        await s.commit()

    ok, _, data = await buy_item_transaction(701012, "ApiFatal")
    assert ok
    tick = await fulfill_processing_order_by_id(data["order_id"])
    assert tick.status == "refunded"

    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == data["order_id"]))).scalar_one()
        assert order.status == OrderStatus.REFUNDED
        user = (await s.execute(select(User).where(User.telegram_id == 701012))).scalar_one()
        assert user.balance == rub_to_cents(Decimal("5000"))


@pytest.mark.asyncio
async def test_gift_recipient_gets_value(user_factory, item_factory):
    await user_factory(telegram_id=701020, balance=5000)
    await user_factory(telegram_id=701021, balance=0)
    await item_factory(name="GiftOk", price=10, values=[("gift-val", False)])
    async with Database().session() as s:
        goods = (await s.execute(select(Goods).where(Goods.name == "GiftOk"))).scalar_one()
        goods.allows_gift = True
        await s.commit()

    ok, msg, data = await buy_item_transaction(
        701020, "GiftOk", gift_recipient_telegram_id=701021
    )
    assert ok and msg == "success"

    async with Database().session() as s:
        bg = (
            await s.execute(select(BoughtGoods).where(BoughtGoods.order_id == data["order_id"]))
        ).scalar_one()
        assert bg.buyer_id == 701021
        assert bg.value == "gift-val"


@pytest.mark.asyncio
async def test_api_without_link_rejected(user_factory, category_factory):
    await category_factory("ApiCat9")
    await user_factory(telegram_id=701030, balance=5000)
    await create_item("ApiNoLink", "d", 10, "ApiCat9", fulfillment_type=FulfillmentType.API)

    ok, msg, _ = await buy_item_transaction(701030, "ApiNoLink")
    assert ok is False and msg == "no_provider_link"
