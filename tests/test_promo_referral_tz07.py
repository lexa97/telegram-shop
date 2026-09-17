"""ТЗ-07: промо (min order, per-user limit, race) и реферал на заказах."""

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from bot.database import Database
from bot.database.methods.orders import (
    create_order_with_snapshot,
    manual_refund_order,
    transition_order,
    compute_profit_cents,
)
from bot.database.methods.transactions import (
    buy_item_transaction,
    process_payment_with_referral,
    redeem_balance_promo,
)
from bot.database.models.main import PromoCodes, PromoCodeUsages, ReferralEarnings, User
from bot.database.models.orders import Order, OrderStatus
from bot.misc.services.referral import credit_referral_for_order
from bot.money import rub_to_cents
from tests.test_promo_validation import _make_promo


@pytest.mark.asyncio
async def test_min_order_blocks_discount(user_factory, item_factory):
    await user_factory(telegram_id=870001, balance=1000)
    await item_factory(name="MINO1", price=50, values=[("v", False)])
    await _make_promo("MINO", "percent", "50", min_order_cents=rub_to_cents(100))
    ok, msg, _ = await buy_item_transaction(870001, "MINO1", promo_code="MINO")
    assert (ok, msg) == (False, "promo_min_order")


@pytest.mark.asyncio
async def test_max_uses_per_user_allows_two(user_factory, item_factory):
    await user_factory(telegram_id=870002, balance=5000)
    await item_factory(name="MU1", price=10, values=[("a", False), ("b", False), ("c", False)])
    await _make_promo("TWICE", "percent", "10", max_uses_per_user=2)
    for _ in range(2):
        ok, msg, _ = await buy_item_transaction(870002, "MU1", promo_code="TWICE")
        assert ok, msg
    ok, msg, _ = await buy_item_transaction(870002, "MU1", promo_code="TWICE")
    assert (ok, msg) == (False, "promo_already_used")


@pytest.mark.asyncio
async def test_redeem_global_max_uses_enforced(user_factory):
    await user_factory(telegram_id=870003, balance=0)
    await _make_promo("RACE", "balance", "5", max_uses=1, current_uses=0)

    ok1, _, amount = await redeem_balance_promo("RACE", 870003)
    ok2, err, _ = await redeem_balance_promo("RACE", 870003)
    assert ok1 and amount == rub_to_cents(5)
    assert ok2 is False
    assert err == "promo.max_uses_reached"


@pytest.mark.asyncio
@pytest.mark.skip(reason="SQLite test DB does not serialize concurrent FOR UPDATE; run on Postgres in CI integration.")
async def test_redeem_last_use_race_parallel(user_factory):
    await user_factory(telegram_id=870099, balance=0)
    await _make_promo("RACEP", "balance", "5", max_uses=1, current_uses=0)

    results = await asyncio.gather(
        redeem_balance_promo("RACEP", 870099),
        redeem_balance_promo("RACEP", 870099),
    )
    assert sum(1 for ok, _, _ in results if ok) == 1


@pytest.mark.asyncio
async def test_topup_no_referral_earnings(user_factory):
    await user_factory(telegram_id=870010, balance=0)
    await user_factory(telegram_id=870011, balance=0, referral_id=870010)
    ok, _ = await process_payment_with_referral(
        870011,
        rub_to_cents(200),
        "test",
        "tz07-noref-1",
        referral_percent=10,
    )
    assert ok
    async with Database().session() as s:
        n = (
            await s.execute(select(func.count()).select_from(ReferralEarnings))
        ).scalar()
        assert n == 0


@pytest.mark.asyncio
async def test_referral_on_completed_order(monkeypatch, user_factory):
    monkeypatch.setattr("bot.misc.services.referral.EnvKeys.REFERRAL_PERCENT", 10)
    async with Database().session() as s:
        s.add(User(telegram_id=870020, balance=0))
        s.add(User(telegram_id=870021, balance=0, referral_id=870020))
        from bot.database.models.main import Categories, Goods

        s.add(Categories(name="c-tz07"))
        await s.flush()
        cat = (await s.execute(select(Categories).where(Categories.name == "c-tz07"))).scalar_one()
        goods = Goods(
            name="ref-item",
            price=rub_to_cents(Decimal("100")),
            description="x",
            category_id=cat.id,
        )
        s.add(goods)
        await s.flush()
        order = await create_order_with_snapshot(
            s,
            user_id=870021,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("100.00"),
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await transition_order(s, order, OrderStatus.COMPLETED)
        await s.commit()
        oid = order.id

    async with Database().session() as s:
        ref = (await s.execute(select(User).where(User.telegram_id == 870020))).scalar_one()
        assert ref.balance == rub_to_cents(10)
        earning = (
            await s.execute(select(ReferralEarnings).where(ReferralEarnings.order_id == oid))
        ).scalar_one()
        assert earning.amount == rub_to_cents(10)
        row = (await s.execute(select(Order).where(Order.id == oid))).scalar_one()
        assert row.referral_amount_cents == rub_to_cents(10)
        assert row.profit_cents == compute_profit_cents(
            row.total_cents, row.cost_cents, row.fee_cents, row.referral_amount_cents
        )


@pytest.mark.asyncio
async def test_referral_credit_idempotent(monkeypatch, user_factory):
    monkeypatch.setattr("bot.misc.services.referral.EnvKeys.REFERRAL_PERCENT", 10)
    async with Database().session() as s:
        s.add(User(telegram_id=870030, balance=0))
        s.add(User(telegram_id=870031, balance=0, referral_id=870030))
        from bot.database.models.main import Categories, Goods

        s.add(Categories(name="c-tz07b"))
        await s.flush()
        cat = (await s.execute(select(Categories).where(Categories.name == "c-tz07b"))).scalar_one()
        goods = Goods(
            name="ref-item-2",
            price=rub_to_cents(Decimal("50")),
            description="x",
            category_id=cat.id,
        )
        s.add(goods)
        await s.flush()
        order = await create_order_with_snapshot(
            s,
            user_id=870031,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("50.00"),
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await transition_order(s, order, OrderStatus.COMPLETED)
        await credit_referral_for_order(s, order)
        await s.commit()

    async with Database().session() as s:
        n = (
            await s.execute(
                select(func.count()).select_from(ReferralEarnings).where(
                    ReferralEarnings.referral_id == 870031
                )
            )
        ).scalar()
        assert n == 1


@pytest.mark.asyncio
async def test_refund_stornos_referral(monkeypatch):
    monkeypatch.setattr("bot.misc.services.referral.EnvKeys.REFERRAL_PERCENT", 10)
    async with Database().session() as s:
        s.add(User(telegram_id=870040, balance=0))
        s.add(User(telegram_id=870041, balance=0, referral_id=870040))
        from bot.database.models.main import Categories, Goods

        s.add(Categories(name="c-tz07c"))
        await s.flush()
        cat = (await s.execute(select(Categories).where(Categories.name == "c-tz07c"))).scalar_one()
        goods = Goods(
            name="ref-item-3",
            price=rub_to_cents(Decimal("80")),
            description="x",
            category_id=cat.id,
        )
        s.add(goods)
        await s.flush()
        order = await create_order_with_snapshot(
            s,
            user_id=870041,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("80.00"),
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await transition_order(s, order, OrderStatus.COMPLETED)
        await s.commit()
        oid = order.id

    async with Database().session() as s:
        await manual_refund_order(s, oid, operator_id=1)
        await s.commit()

    async with Database().session() as s:
        ref = (await s.execute(select(User).where(User.telegram_id == 870040))).scalar_one()
        assert ref.balance == 0
        n = (
            await s.execute(
                select(func.count()).select_from(ReferralEarnings).where(
                    ReferralEarnings.order_id == oid
                )
            )
        ).scalar()
        assert n == 0
        row = (await s.execute(select(Order).where(Order.id == oid))).scalar_one()
        assert row.referral_amount_cents == 0


@pytest.mark.asyncio
async def test_buy_records_promo_usage_with_order_id(user_factory, item_factory):
    await user_factory(telegram_id=870050, balance=1000)
    await item_factory(name="PU1", price=100, values=[("v", False)])
    await _make_promo("ORDP", "fixed", "10")
    ok, msg, data = await buy_item_transaction(870050, "PU1", promo_code="ORDP")
    assert ok, msg
    async with Database().session() as s:
        usage = (
            await s.execute(
                select(PromoCodeUsages).where(PromoCodeUsages.user_id == 870050)
            )
        ).scalar_one()
        assert usage.order_id is not None
        promo = (await s.execute(select(PromoCodes).where(PromoCodes.code == "ORDP"))).scalar_one()
        assert promo.current_uses == 1
