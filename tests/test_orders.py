"""ТЗ-02: заказы — переходы статусов, snapshot, refund, cancel."""

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from bot.database import Database
from bot.database.methods.orders import (
    OrderCancelForbidden,
    OrderTransitionError,
    allowed_next_statuses,
    can_transition,
    compute_profit_cents,
    create_order_with_snapshot,
    expire_created_if_due,
    manual_refund_order,
    transition_order,
    user_cancel_order,
)
from bot.money import rub_to_cents
from bot.database.models.main import Categories, Goods, User
from bot.database.models.orders import Order, OrderStatus, OrderStatusHistory


async def _seed_user_and_goods(s, user_id: int = 500001, price: Decimal = Decimal("100.00")):
    s.add(User(telegram_id=user_id, balance=rub_to_cents(Decimal("500.00"))))
    s.add(Categories(name=f"cat-{user_id}"))
    await s.flush()
    cat = (await s.execute(select(Categories).where(Categories.name == f"cat-{user_id}"))).scalar_one()
    goods = Goods(
        name=f"item-{user_id}",
        price=rub_to_cents(price),
        description="test",
        category_id=cat.id,
    )
    s.add(goods)
    await s.flush()
    return user_id, goods


@pytest.mark.parametrize(
    "from_status,to_status,ok",
    [
        (OrderStatus.CREATED, OrderStatus.PROCESSING, True),
        (OrderStatus.CREATED, OrderStatus.EXPIRED, True),
        (OrderStatus.CREATED, OrderStatus.COMPLETED, False),
        (OrderStatus.PROCESSING, OrderStatus.COMPLETED, True),
        (OrderStatus.PROCESSING, OrderStatus.FAILED, True),
        (OrderStatus.COMPLETED, OrderStatus.REFUNDED, True),
        (OrderStatus.FAILED, OrderStatus.REFUNDED, True),
        (OrderStatus.REFUNDED, OrderStatus.COMPLETED, False),
        (OrderStatus.EXPIRED, OrderStatus.CREATED, False),
        (OrderStatus.COMPLETED, OrderStatus.FAILED, False),
    ],
)
def test_transition_matrix(from_status, to_status, ok):
    assert can_transition(from_status, to_status) is ok


def test_all_statuses_have_allowed_set():
    for st in OrderStatus.ALL:
        assert isinstance(allowed_next_statuses(st), frozenset)


def test_compute_profit():
    assert compute_profit_cents(10000, 3000, 500, 200) == 6300


def test_expire_created_pure():
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    past = now - datetime.timedelta(hours=1)
    future = now + datetime.timedelta(hours=1)
    assert expire_created_if_due(OrderStatus.CREATED, past, now) == OrderStatus.EXPIRED
    assert expire_created_if_due(OrderStatus.CREATED, future, now) is None
    assert expire_created_if_due(OrderStatus.PROCESSING, past, now) is None


@pytest.mark.asyncio
async def test_snapshot_immune_to_goods_price_change():
    async with Database().session() as s:
        user_id, goods = await _seed_user_and_goods(s, price=Decimal("50.00"))
        order = await create_order_with_snapshot(
            s,
            user_id=user_id,
            goods_id=goods.id,
            quantity=2,
            unit_price_rub=Decimal("50.00"),
            discount_cents=0,
        )
        await s.commit()
        order_id = order.id
        total_before = order.total_cents

    async with Database().session() as s:
        await s.execute(
            update(Goods).where(Goods.id == goods.id).values(price=rub_to_cents(Decimal("999.99")))
        )
        await s.commit()

    async with Database().session() as s:
        row = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert row.total_cents == total_before == 10000
        assert row.price_cents == 5000


@pytest.mark.asyncio
async def test_illegal_transition_raises():
    async with Database().session() as s:
        user_id, goods = await _seed_user_and_goods(s)
        order = await create_order_with_snapshot(
            s,
            user_id=user_id,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("10.00"),
        )
        with pytest.raises(OrderTransitionError):
            await transition_order(s, order, OrderStatus.COMPLETED)


@pytest.mark.asyncio
async def test_completed_sets_profit():
    async with Database().session() as s:
        user_id, goods = await _seed_user_and_goods(s)
        order = await create_order_with_snapshot(
            s,
            user_id=user_id,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("100.00"),
            cost_cents=4000,
            fee_cents=500,
            referral_amount_cents=100,
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await transition_order(s, order, OrderStatus.COMPLETED)
        assert order.profit_cents == compute_profit_cents(10000, 4000, 500, 100)
        await s.flush()
        hist = (
            await s.execute(
                select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
            )
        ).scalars().all()
        assert len(hist) >= 3


@pytest.mark.asyncio
async def test_refund_idempotent():
    async with Database().session() as s:
        user_id, goods = await _seed_user_and_goods(s)
        order = await create_order_with_snapshot(
            s,
            user_id=user_id,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("25.00"),
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await transition_order(s, order, OrderStatus.COMPLETED)
        await s.commit()
        oid = order.id

    async with Database().session() as s:
        _, credited1 = await manual_refund_order(s, oid, operator_id=999999)
        user_after_first = (
            await s.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one()
        bal_after_first = user_after_first.balance
        await s.commit()

    async with Database().session() as s:
        _, credited2 = await manual_refund_order(s, oid, operator_id=999999)
        user_after_second = (
            await s.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one()
        await s.commit()

    assert credited1 is True
    assert credited2 is False
    assert user_after_second.balance == bal_after_first


@pytest.mark.asyncio
async def test_user_cannot_cancel_paid_order():
    async with Database().session() as s:
        user_id, goods = await _seed_user_and_goods(s)
        order = await create_order_with_snapshot(
            s,
            user_id=user_id,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("10.00"),
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await s.commit()
        oid = order.id

    async with Database().session() as s:
        with pytest.raises(OrderCancelForbidden):
            await user_cancel_order(s, oid, user_id)


@pytest.mark.asyncio
async def test_user_can_cancel_created():
    async with Database().session() as s:
        user_id, goods = await _seed_user_and_goods(s)
        order = await create_order_with_snapshot(
            s,
            user_id=user_id,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("10.00"),
        )
        await s.commit()
        oid = order.id

    async with Database().session() as s:
        updated = await user_cancel_order(s, oid, user_id)
        assert updated.status == OrderStatus.EXPIRED
