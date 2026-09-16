"""Stock allocation, reservation, and gift rules for STOCK fulfillment."""

from __future__ import annotations

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.enums import FulfillmentType, StockUnitStatus
from bot.database.models.main import Goods, ItemValues


class StockAllocationError(Exception):
    """Stock layer rejected allocation (user-facing code in ``code``)."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def assert_gift_purchase_allowed(goods: Goods, gift_recipient_telegram_id: int | None) -> None:
    if gift_recipient_telegram_id is None:
        return
    if not goods.allows_gift:
        raise StockAllocationError("gift_not_allowed")


def _use_skip_locked(session: AsyncSession) -> bool:
    bind = session.get_bind()
    name = getattr(bind, "dialect", None)
    if name is None:
        sync = bind.sync_engine if hasattr(bind, "sync_engine") else bind
        dialect_name = sync.dialect.name
    else:
        dialect_name = name.name
    return dialect_name == "postgresql"


async def consume_stock_units(
    session: AsyncSession,
    goods: Goods,
    quantity: int = 1,
) -> list[str]:
    """Claim ``quantity`` deliverable values for immediate sale (balance checkout).

    Finite units are removed from stock after claim (same as legacy delete-on-buy).
    Infinite template rows stay AVAILABLE.
    """
    if quantity <= 0:
        return []
    if goods.fulfillment_type == FulfillmentType.API:
        raise StockAllocationError("api_fulfillment")

    skip = _use_skip_locked(session)

    inf = (
        await session.execute(
            select(ItemValues)
            .where(
                ItemValues.item_id == goods.id,
                ItemValues.is_infinity.is_(True),
            )
            .limit(1)
            .with_for_update()
        )
    ).scalars().first()
    if inf:
        return [inf.value] * quantity

    stmt = (
        select(ItemValues.id, ItemValues.value)
        .where(
            ItemValues.item_id == goods.id,
            ItemValues.is_infinity.is_(False),
            ItemValues.status == StockUnitStatus.AVAILABLE,
        )
        .order_by(ItemValues.id)
        .limit(quantity)
    )
    if skip:
        stmt = stmt.with_for_update(skip_locked=True)
    else:
        stmt = stmt.with_for_update()

    rows = (await session.execute(stmt)).all()
    if len(rows) < quantity:
        raise StockAllocationError("out_of_stock")

    values: list[str] = []
    for row_id, row_value in rows:
        deleted = await session.execute(
            sa_delete(ItemValues).where(
                ItemValues.id == row_id,
                ItemValues.status == StockUnitStatus.AVAILABLE,
            )
        )
        if deleted.rowcount != 1:
            raise StockAllocationError("out_of_stock")
        values.append(row_value)
    return values


async def reserve_stock_units(
    session: AsyncSession,
    goods: Goods,
    order_id: int,
    quantity: int = 1,
) -> list[str]:
    """Reserve finite units for an unpaid/processing order (TTL path, ТЗ-02/06)."""
    if goods.fulfillment_type == FulfillmentType.API:
        raise StockAllocationError("api_fulfillment")
    if quantity <= 0:
        return []

    skip = _use_skip_locked(session)

    inf = (
        await session.execute(
            select(ItemValues)
            .where(
                ItemValues.item_id == goods.id,
                ItemValues.is_infinity.is_(True),
            )
            .limit(1)
            .with_for_update()
        )
    ).scalars().first()
    if inf:
        return [inf.value] * quantity

    values: list[str] = []
    for _ in range(quantity):
        stmt = (
            select(ItemValues.id, ItemValues.value)
            .where(
                ItemValues.item_id == goods.id,
                ItemValues.is_infinity.is_(False),
                ItemValues.status == StockUnitStatus.AVAILABLE,
            )
            .order_by(ItemValues.id)
            .limit(1)
        )
        if skip:
            stmt = stmt.with_for_update(skip_locked=True)
        else:
            stmt = stmt.with_for_update()

        row = (await session.execute(stmt)).first()
        if not row:
            raise StockAllocationError("out_of_stock")
        row_id, row_value = row
        updated = await session.execute(
            update(ItemValues)
            .where(
                ItemValues.id == row_id,
                ItemValues.status == StockUnitStatus.AVAILABLE,
            )
            .values(status=StockUnitStatus.RESERVED, reserved_order_id=order_id)
        )
        if updated.rowcount != 1:
            raise StockAllocationError("out_of_stock")
        values.append(row_value)
    return values


async def release_stock_reservations(session: AsyncSession, order_id: int) -> int:
    """Return RESERVED units for ``order_id`` to AVAILABLE (EXPIRED/FAILED)."""
    result = await session.execute(
        update(ItemValues)
        .where(
            ItemValues.reserved_order_id == order_id,
            ItemValues.status == StockUnitStatus.RESERVED,
        )
        .values(status=StockUnitStatus.AVAILABLE, reserved_order_id=None)
    )
    return result.rowcount or 0


async def count_finite_available_units(session: AsyncSession, goods_id: int) -> int:
    from sqlalchemy import func

    return (
        await session.execute(
            select(func.count())
            .select_from(ItemValues)
            .where(
                ItemValues.item_id == goods_id,
                ItemValues.is_infinity.is_(False),
                ItemValues.status == StockUnitStatus.AVAILABLE,
            )
        )
    ).scalar() or 0


def stock_unit_available_clause():
    """SQLAlchemy filter: rows that count as sellable stock."""
    from sqlalchemy import or_

    return or_(
        ItemValues.is_infinity.is_(True),
        ItemValues.status == StockUnitStatus.AVAILABLE,
    )
