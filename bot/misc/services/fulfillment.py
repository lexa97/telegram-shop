"""Order checkout and fulfillment (ТЗ-06). Handlers stay thin; API HTTP outside long DB locks."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.catalog.enums import FulfillmentType
from bot.catalog.stock import (
    StockAllocationError,
    assert_gift_purchase_allowed,
    consume_stock_units,
)
from bot.database.methods.orders import (
    OrderTransitionError,
    create_order_with_snapshot,
    transition_order,
)
from bot.database.models.fulfillment_providers import GoodsProviderLink
from bot.database.models.main import BoughtGoods, Goods, Operations, User
from bot.database.models.orders import DeliveryType, Order, OrderStatus
from bot.money import cents_to_float_rub
from bot.providers.errors import ProviderFatalError, ProviderRetryableError
from bot.providers.fulfillment import create_external_order
from bot.providers.links import select_primary_link_for_session


def _max_fulfillment_retries(link: GoodsProviderLink) -> int:
    if link.retry_count is not None:
        return max(1, int(link.retry_count))
    provider = link.provider
    return max(1, int(provider.default_retry_count or 3))


class FulfillmentError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class FulfillTickResult:
    status: str  # noop | completed | pending | refunded | retry


def _delivery_recipient_telegram_id(order: Order) -> int:
    if order.gift_telegram_id is not None:
        return int(order.gift_telegram_id)
    return int(order.user_id)


def _resolve_delivery_type(goods: Goods, gift_recipient_telegram_id: int | None) -> str:
    if gift_recipient_telegram_id is not None:
        return DeliveryType.GIFT
    if goods.fulfillment_type == FulfillmentType.API:
        return DeliveryType.API
    return DeliveryType.STOCK


async def _record_bought_units(
    session: AsyncSession,
    order: Order,
    goods: Goods,
    values: list[str],
    unit_prices_cents: list[int],
) -> list[BoughtGoods]:
    recipient = _delivery_recipient_telegram_id(order)
    rows: list[BoughtGoods] = []
    for value, unit_price in zip(values, unit_prices_cents):
        row = BoughtGoods(
            item_name=goods.name,
            value=value,
            price=unit_price,
            buyer_id=recipient,
            bought_datetime=datetime.datetime.now(datetime.timezone.utc),
            unique_id=uuid4().int >> 65,
            order_id=order.id,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


def _split_amount(total_cents: int, n: int) -> list[int]:
    if n <= 0:
        return []
    base, extra = divmod(int(total_cents), n)
    return [base + (1 if i < extra else 0) for i in range(n)]


async def _credit_refund(session: AsyncSession, order: Order) -> None:
    user = (
        await session.execute(
            select(User).where(User.telegram_id == order.user_id).with_for_update()
        )
    ).scalar_one()
    user.balance += order.total_cents
    session.add(
        Operations(
            user_id=order.user_id,
            operation_value=order.total_cents,
            operation_time=datetime.datetime.now(datetime.timezone.utc),
        )
    )


async def refund_failed_order(session: AsyncSession, order: Order, *, actor_id: int | None = None) -> Order:
    """FAILED → REFUNDED with balance restore (ТЗ-06 auto-refund)."""
    if order.status == OrderStatus.REFUNDED:
        return order
    if order.status != OrderStatus.FAILED:
        raise OrderTransitionError(f"refund_not_allowed:{order.status}")
    await _credit_refund(session, order)
    return await transition_order(session, order, OrderStatus.REFUNDED, actor_id=actor_id)


async def complete_stock_order(
    session: AsyncSession,
    order: Order,
    goods: Goods,
    delivered_values: list[str],
) -> list[BoughtGoods]:
    """PROCESSING stock order → BoughtGoods + COMPLETED."""
    if order.status == OrderStatus.COMPLETED:
        existing = (
            await session.execute(select(BoughtGoods).where(BoughtGoods.order_id == order.id))
        ).scalars().all()
        return list(existing)
    if order.status != OrderStatus.PROCESSING:
        raise FulfillmentError(f"invalid_status:{order.status}")

    unit_prices = _split_amount(order.total_cents, len(delivered_values))
    rows = await _record_bought_units(session, order, goods, delivered_values, unit_prices)
    await transition_order(session, order, OrderStatus.COMPLETED, actor_id=order.user_id)
    return rows


async def fulfill_processing_order(
    session: AsyncSession,
    order_id: int,
    *,
    link: GoodsProviderLink | None = None,
) -> FulfillTickResult:
    """Idempotent API fulfillment tick (worker / tests)."""
    order = (
        await session.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.goods), selectinload(Order.bought_goods))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not order:
        raise FulfillmentError("order_not_found")

    if order.status == OrderStatus.COMPLETED:
        return FulfillTickResult(status="noop")
    if order.status != OrderStatus.PROCESSING:
        return FulfillTickResult(status="noop")

    already = (
        await session.execute(
            select(BoughtGoods).where(BoughtGoods.order_id == order.id).limit(1)
        )
    ).scalar_one_or_none()
    if already is not None:
        if order.status != OrderStatus.COMPLETED:
            await transition_order(session, order, OrderStatus.COMPLETED, actor_id=order.user_id)
        return FulfillTickResult(status="noop")

    if order.delivery_type == DeliveryType.STOCK:
        raise FulfillmentError("stock_not_in_worker")

    goods = order.goods
    if link is None:
        if order.provider_id:
            link = (
                await session.execute(
                    select(GoodsProviderLink)
                    .where(
                        GoodsProviderLink.goods_id == goods.id,
                        GoodsProviderLink.provider_id == order.provider_id,
                    )
                    .options(selectinload(GoodsProviderLink.provider))
                    .limit(1)
                )
            ).scalars().first()
        if link is None:
            link = await select_primary_link_for_session(session, goods.id)
    if link is None:
        await transition_order(session, order, OrderStatus.FAILED, actor_id=order.user_id)
        await refund_failed_order(session, order, actor_id=order.user_id)
        return FulfillTickResult(status="refunded")

    try:
        provider_order = await create_external_order(session, order, link)
    except ProviderRetryableError:
        order.fulfillment_attempt_count = int(order.fulfillment_attempt_count or 0) + 1
        if order.fulfillment_attempt_count >= _max_fulfillment_retries(link):
            await transition_order(session, order, OrderStatus.FAILED, actor_id=order.user_id)
            await refund_failed_order(session, order, actor_id=order.user_id)
            return FulfillTickResult(status="refunded")
        return FulfillTickResult(status="retry")
    except ProviderFatalError:
        await transition_order(session, order, OrderStatus.FAILED, actor_id=order.user_id)
        await refund_failed_order(session, order, actor_id=order.user_id)
        return FulfillTickResult(status="refunded")

    delivery = provider_order.delivery_value or order.fulfillment_payload
    if not delivery:
        if provider_order.completed:
            delivery = order.fulfillment_payload
        if not delivery:
            return FulfillTickResult(status="pending")

    unit_prices = _split_amount(order.total_cents, order.quantity)
    values = [delivery] * order.quantity if order.quantity > 1 else [delivery]
    await _record_bought_units(session, order, goods, values, unit_prices)
    await transition_order(session, order, OrderStatus.COMPLETED, actor_id=order.user_id)
    return FulfillTickResult(status="completed")


async def fulfill_processing_order_by_id(order_id: int) -> FulfillTickResult:
    from bot.database import Database

    async with Database().session() as session:
        result = await fulfill_processing_order(session, order_id)
        return result


async def begin_paid_order(
    session: AsyncSession,
    *,
    user: User,
    goods: Goods,
    quantity: int,
    unit_price_cents: int,
    discount_cents: int,
    gift_recipient_telegram_id: int | None,
    cost_cents: int = 0,
) -> Order:
    """Create order, deduct balance, move to PROCESSING (caller completes stock/API)."""
    line_total = unit_price_cents * quantity
    total_cents = max(0, line_total - discount_cents)
    if user.balance < total_cents:
        raise FulfillmentError("insufficient_funds")

    assert_gift_purchase_allowed(goods, gift_recipient_telegram_id)
    delivery_type = _resolve_delivery_type(goods, gift_recipient_telegram_id)

    unit_rub = Decimal(unit_price_cents) / Decimal("100")
    order = await create_order_with_snapshot(
        session,
        user_id=user.telegram_id,
        goods_id=goods.id,
        quantity=quantity,
        unit_price_rub=unit_rub,
        discount_cents=discount_cents,
        cost_cents=cost_cents,
        delivery_type=delivery_type,
        gift_telegram_id=gift_recipient_telegram_id,
    )
    user.balance -= total_cents
    await transition_order(session, order, OrderStatus.PROCESSING, actor_id=user.telegram_id)
    return order


async def purchase_stock_line(
    session: AsyncSession,
    order: Order,
    goods: Goods,
    quantity: int,
    *,
    delivered_values: list[str] | None = None,
) -> list[BoughtGoods]:
    delivered = delivered_values or await consume_stock_units(session, goods, quantity)
    return await complete_stock_order(session, order, goods, delivered)


async def purchase_api_line(
    session: AsyncSession,
    order: Order,
    goods: Goods,
) -> None:
    link = await select_primary_link_for_session(session, goods.id)
    if link is None:
        raise FulfillmentError("no_provider_link")
    order.provider_id = link.provider_id
    if link.cost_cents:
        order.cost_cents = link.cost_cents


def purchase_result_from_order(
    order: Order,
    goods: Goods,
    bought_rows: list[BoughtGoods],
    user_balance_cents: int,
    discount_info: dict | None = None,
) -> dict:
    primary = bought_rows[0] if bought_rows else None
    data = {
        "item_name": goods.name,
        "value": primary.value if primary else None,
        "price": cents_to_float_rub(order.total_cents),
        "new_balance": cents_to_float_rub(user_balance_cents),
        "order_id": order.id,
        "order_status": order.status,
    }
    if primary:
        data["unique_id"] = primary.unique_id
        data["bought_id"] = primary.id
        data["bought_datetime"] = primary.bought_datetime.isoformat()
    if discount_info:
        data["discount"] = discount_info
    return data
