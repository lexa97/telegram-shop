"""ТЗ-09: тикеты поддержки."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from bot.database import Database
from bot.database.methods.orders import create_order_with_snapshot, transition_order
from bot.database.methods.support import (
    SupportError,
    add_user_message,
    create_ticket,
    get_ticket_for_user,
    staff_reply,
)
from bot.database.models.main import Categories, Goods, User
from bot.database.models.orders import OrderStatus
from bot.database.models.support import SupportMessage, SupportTicket
from bot.money import rub_to_cents


async def _seed_user_and_order(user_id: int = 910001):
    async with Database().session() as s:
        existing = (
            await s.execute(select(User.telegram_id).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        if existing is None:
            s.add(User(telegram_id=user_id, balance=0))
        s.add(Categories(name=f"cat-{user_id}"))
        await s.flush()
        cat = (await s.execute(select(Categories).where(Categories.name == f"cat-{user_id}"))).scalar_one()
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
async def test_user_creates_ticket_and_history(user_factory):
    await user_factory(telegram_id=910010)
    async with Database().session() as s:
        ticket = await create_ticket(s, 910010, "Hello support")
        await s.commit()
        tid = ticket.id

    async with Database().session() as s:
        loaded = await get_ticket_for_user(s, tid, 910010)
        assert loaded is not None
        assert len(loaded.messages) == 1
        assert loaded.messages[0].body == "Hello support"

    async with Database().session() as s:
        await add_user_message(s, tid, 910010, "Follow-up")
        await s.commit()

    async with Database().session() as s:
        loaded = await get_ticket_for_user(s, tid, 910010)
        assert len(loaded.messages) == 2


@pytest.mark.asyncio
async def test_one_active_ticket_per_user(user_factory):
    await user_factory(telegram_id=910011)
    async with Database().session() as s:
        await create_ticket(s, 910011, "First")
        await s.commit()

    async with Database().session() as s:
        with pytest.raises(SupportError) as exc:
            await create_ticket(s, 910011, "Second")
        assert exc.value.code == "support.active_ticket_exists"


@pytest.mark.asyncio
async def test_user_cannot_see_other_ticket(user_factory):
    await user_factory(telegram_id=910020)
    await user_factory(telegram_id=910021)
    async with Database().session() as s:
        ticket = await create_ticket(s, 910020, "Private")
        await s.commit()
        tid = ticket.id

    async with Database().session() as s:
        assert await get_ticket_for_user(s, tid, 910021) is None


@pytest.mark.asyncio
async def test_staff_reply_persists(user_factory):
    await user_factory(telegram_id=910030)
    async with Database().session() as s:
        ticket = await create_ticket(s, 910030, "Need help")
        await s.commit()
        tid = ticket.id

    async with Database().session() as s:
        msg = await staff_reply(s, tid, 900001, "We are on it")
        await s.commit()

    assert msg.author_role == "staff"
    async with Database().session() as s:
        row = (await s.execute(select(SupportTicket).where(SupportTicket.id == tid))).scalar_one()
        assert row.status == "pending"
        msgs = (await s.execute(select(SupportMessage).where(SupportMessage.ticket_id == tid))).scalars().all()
        assert len(msgs) == 2


@pytest.mark.asyncio
async def test_ticket_with_order_id(user_factory):
    await user_factory(telegram_id=910040)
    oid = await _seed_user_and_order(910040)
    async with Database().session() as s:
        ticket = await create_ticket(s, 910040, "Order issue", linked_order_id=oid)
        await s.commit()
        assert ticket.linked_order_id == oid

@pytest.mark.asyncio
async def test_invalid_order_on_create(user_factory):
    await user_factory(telegram_id=910041)
    async with Database().session() as s:
        with pytest.raises(SupportError) as exc:
            await create_ticket(s, 910041, "Bad order", linked_order_id=999999)
        assert exc.value.code == "support.order_not_found"


@pytest.mark.asyncio
async def test_close_ticket(user_factory):
    from bot.database.methods.support import close_ticket_by_user

    await user_factory(telegram_id=910051)
    async with Database().session() as s:
        ticket = await create_ticket(s, 910051, "Close me")
        await s.commit()
        tid = ticket.id

    async with Database().session() as s:
        await close_ticket_by_user(s, tid, 910051)
        await s.commit()

    async with Database().session() as s:
        with pytest.raises(SupportError) as exc:
            await add_user_message(s, tid, 910051, "nope")
        assert exc.value.code == "support.ticket_closed"
