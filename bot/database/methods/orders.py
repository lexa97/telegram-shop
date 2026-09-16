"""Order lifecycle: status transitions, snapshot creation, refund, user cancel."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.read import invalidate_user_cache
from bot.database.methods.cache_utils import safe_create_task
from bot.database.models.main import Operations, User
from bot.database.models.orders import DeliveryType, Order, OrderStatus, OrderStatusHistory
from bot.money import rub_to_cents


class OrderError(Exception):
    """Base order domain error."""


class OrderTransitionError(OrderError):
    """Illegal status transition."""


class OrderCancelForbidden(OrderError):
    """User cannot cancel this order."""


# Allowed transitions (terminal states have no outgoing edges).
_ALLOWED: dict[str, frozenset[str]] = {
    OrderStatus.CREATED: frozenset(
        {OrderStatus.PROCESSING, OrderStatus.EXPIRED}
    ),
    OrderStatus.PROCESSING: frozenset(
        {OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.EXPIRED}
    ),
    OrderStatus.COMPLETED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.FAILED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.EXPIRED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}


def allowed_next_statuses(current: str) -> frozenset[str]:
    return _ALLOWED.get(current, frozenset())


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in allowed_next_statuses(from_status)


def compute_profit_cents(
    total_cents: int,
    cost_cents: int,
    fee_cents: int,
    referral_amount_cents: int,
) -> int:
    return total_cents - cost_cents - fee_cents - referral_amount_cents


def expire_created_if_due(
    status: str,
    expires_at: Optional[datetime.datetime],
    now: datetime.datetime,
) -> Optional[str]:
    """Pure helper: CREATED past TTL → EXPIRED; otherwise None."""
    if status != OrderStatus.CREATED or expires_at is None:
        return None
    if now >= expires_at:
        return OrderStatus.EXPIRED
    return None


async def _append_history(
    session: AsyncSession,
    order: Order,
    from_status: Optional[str],
    to_status: str,
    actor_id: Optional[int],
) -> None:
    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
        )
    )
    await session.flush()


async def transition_order(
    session: AsyncSession,
    order: Order,
    to_status: str,
    *,
    actor_id: Optional[int] = None,
    now: Optional[datetime.datetime] = None,
) -> Order:
    """Apply a legal status transition and record history."""
    if to_status not in OrderStatus.ALL:
        raise OrderTransitionError(f"unknown_status:{to_status}")
    from_status = order.status
    if not can_transition(from_status, to_status):
        raise OrderTransitionError(f"illegal:{from_status}->{to_status}")

    order.status = to_status
    if to_status in (OrderStatus.EXPIRED, OrderStatus.FAILED):
        from bot.catalog.stock import release_stock_reservations

        await release_stock_reservations(session, order.id)
    if to_status == OrderStatus.COMPLETED:
        order.profit_cents = compute_profit_cents(
            order.total_cents,
            order.cost_cents,
            order.fee_cents,
            order.referral_amount_cents,
        )
        order.completed_at = now or datetime.datetime.now(datetime.timezone.utc)
    await _append_history(session, order, from_status, to_status, actor_id)
    return order


async def create_order_with_snapshot(
    session: AsyncSession,
    *,
    user_id: int,
    goods_id: int,
    quantity: int,
    unit_price_rub: Decimal,
    discount_cents: int = 0,
    cost_cents: int = 0,
    fee_cents: int = 0,
    referral_amount_cents: int = 0,
    delivery_type: str = DeliveryType.STOCK,
    expires_at: Optional[datetime.datetime] = None,
    provider_id: Optional[int] = None,
    provider_external_order_id: Optional[str] = None,
    gift_telegram_id: Optional[int] = None,
) -> Order:
    """Create CREATED order with frozen financial fields (kopecks)."""
    if quantity <= 0:
        raise OrderError("invalid_quantity")
    unit_cents = rub_to_cents(unit_price_rub)
    line_price_cents = unit_cents * quantity
    total_cents = max(0, line_price_cents - discount_cents)

    order = Order(
        user_id=user_id,
        goods_id=goods_id,
        quantity=quantity,
        price_cents=unit_cents,
        discount_cents=discount_cents,
        total_cents=total_cents,
        cost_cents=cost_cents,
        fee_cents=fee_cents,
        referral_amount_cents=referral_amount_cents,
        status=OrderStatus.CREATED,
        delivery_type=delivery_type,
        provider_id=provider_id,
        provider_external_order_id=provider_external_order_id,
        gift_telegram_id=gift_telegram_id,
        expires_at=expires_at,
    )
    session.add(order)
    await session.flush()
    await _append_history(session, order, None, OrderStatus.CREATED, user_id)
    return order


_PAID_OR_SETTLED = frozenset(
    {
        OrderStatus.PROCESSING,
        OrderStatus.COMPLETED,
        OrderStatus.FAILED,
        OrderStatus.REFUNDED,
    }
)


async def user_cancel_order(session: AsyncSession, order_id: int, user_id: int) -> Order:
    """User may only cancel unpaid CREATED orders (→ EXPIRED)."""
    order = (
        await session.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not order or order.user_id != user_id:
        raise OrderCancelForbidden("not_found")
    if order.status in _PAID_OR_SETTLED:
        raise OrderCancelForbidden("paid_order")
    if order.status != OrderStatus.CREATED:
        raise OrderCancelForbidden("not_cancellable")
    return await transition_order(
        session, order, OrderStatus.EXPIRED, actor_id=user_id
    )


async def manual_refund_order(
    session: AsyncSession,
    order_id: int,
    operator_id: int,
) -> tuple[Order, bool]:
    """
    Operator refund: COMPLETED|FAILED → REFUNDED, credit total to user balance.
    Returns (order, credited) where credited is False if already refunded (idempotent).
    """
    order = (
        await session.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not order:
        raise OrderError("not_found")

    if order.status == OrderStatus.REFUNDED:
        return order, False

    if order.status not in (OrderStatus.COMPLETED, OrderStatus.FAILED):
        raise OrderTransitionError(f"refund_not_allowed:{order.status}")

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
        )
    )

    await transition_order(session, order, OrderStatus.REFUNDED, actor_id=operator_id)
    safe_create_task(invalidate_user_cache(order.user_id))
    return order, True


async def get_order(session: AsyncSession, order_id: int) -> Optional[Order]:
    return (
        await session.execute(select(Order).where(Order.id == order_id))
    ).scalar_one_or_none()
