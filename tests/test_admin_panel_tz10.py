"""ТЗ-10: SQLAdmin panel helpers and stats."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from bot.database import Database
from bot.database.methods.orders import create_order_with_snapshot, transition_order
from bot.database.models.main import Categories, Goods, User
from bot.database.models.orders import Order, OrderStatus
from bot.misc import EnvKeys
from bot.money import rub_to_cents
from bot.web.admin_helpers import (
    aggregate_completed_order_stats,
    mask_gateway_config,
    run_manual_refund,
    validate_json_text,
)


class _Gw:
    config_json = '{"api_key":"secret"}'


def test_validate_json_text_accepts_object():
    assert validate_json_text('{"a": 1}', "cfg") == '{"a": 1}'


def test_validate_json_text_rejects_invalid():
    with pytest.raises(ValueError, match="valid JSON"):
        validate_json_text("{not json", "cfg")


def test_mask_gateway_config_operator_mode(monkeypatch):
    monkeypatch.setattr(EnvKeys, "ADMIN_PANEL_OPERATOR", "1")
    assert mask_gateway_config(_Gw(), "config_json") == "••••••••"


def test_mask_gateway_config_shows_when_not_operator(monkeypatch):
    monkeypatch.setattr(EnvKeys, "ADMIN_PANEL_OPERATOR", "0")
    assert "api_key" in mask_gateway_config(_Gw(), "config_json")


async def _completed_order(user_id: int = 920001):
    async with Database().session() as s:
        if (
            await s.execute(select(User.telegram_id).where(User.telegram_id == user_id))
        ).scalar_one_or_none() is None:
            s.add(User(telegram_id=user_id, balance=0))
        s.add(Categories(name=f"cat-{user_id}"))
        await s.flush()
        cat = (
            await s.execute(select(Categories).where(Categories.name == f"cat-{user_id}"))
        ).scalar_one()
        goods = Goods(
            name=f"g-{user_id}",
            price=rub_to_cents(Decimal("10")),
            description="x",
            category_id=cat.id,
        )
        s.add(goods)
        await s.flush()
        order = await create_order_with_snapshot(
            s,
            user_id=user_id,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("10.00"),
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await transition_order(s, order, OrderStatus.COMPLETED)
        await s.commit()
        return order.id


@pytest.mark.asyncio
async def test_aggregate_completed_order_stats_profit():
    oid = await _completed_order(920002)
    async with Database().session() as s:
        order = (await s.execute(select(Order).where(Order.id == oid))).scalar_one()
        expected_profit = int(order.profit_cents or 0)
        stats = await aggregate_completed_order_stats(s)
    assert stats["completed_orders"] >= 1
    assert stats["profit_cents"] >= expected_profit


@pytest.mark.asyncio
async def test_run_manual_refund_web_helper():
    oid = await _completed_order(920003)
    msg, credited = await run_manual_refund(oid, operator_id=920099)
    assert credited is True
    assert "refunded" in msg.lower()
    _, credited2 = await run_manual_refund(oid, operator_id=920099)
    assert credited2 is False
