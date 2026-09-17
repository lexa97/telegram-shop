"""Referral rewards on completed orders (ТЗ-07)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.audit import log_audit
from bot.database.methods.read import invalidate_user_cache
from bot.database.methods.cache_utils import safe_create_task
from bot.database.models.main import ReferralEarnings, User
from bot.database.models.orders import Order, OrderStatus
from bot.misc import EnvKeys


def _referral_percent() -> int:
    return min(max(int(EnvKeys.REFERRAL_PERCENT or 0), 0), 99)


async def credit_referral_for_order(session: AsyncSession, order: Order) -> int:
    """Idempotent: one ReferralEarnings row per order. Returns credited kopecks."""
    if order.status != OrderStatus.COMPLETED:
        return 0

    existing = (
        await session.execute(
            select(ReferralEarnings).where(ReferralEarnings.order_id == order.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if order.referral_amount_cents != existing.amount:
            order.referral_amount_cents = existing.amount
        return existing.amount

    percent = _referral_percent()
    if percent <= 0:
        return 0

    buyer = (
        await session.execute(
            select(User).where(User.telegram_id == order.user_id).with_for_update()
        )
    ).scalar_one()

    referrer_id = buyer.referral_id
    if not referrer_id or referrer_id == order.user_id:
        return 0

    amount = (int(order.total_cents) * percent) // 100
    if amount <= 0:
        return 0

    referrer = (
        await session.execute(
            select(User).where(User.telegram_id == referrer_id).with_for_update()
        )
    ).scalar_one_or_none()
    if referrer is None:
        return 0

    referrer.balance += amount
    order.referral_amount_cents = amount
    session.add(
        ReferralEarnings(
            referrer_id=referrer_id,
            referral_id=order.user_id,
            amount=amount,
            original_amount=order.total_cents,
            order_id=order.id,
        )
    )
    await log_audit(
        "referral_bonus",
        user_id=referrer_id,
        resource_type="Order",
        resource_id=str(order.id),
        details=f"order_total={order.total_cents}, bonus={amount}",
        session=session,
    )
    safe_create_task(invalidate_user_cache(referrer_id))
    return amount


async def reverse_referral_for_order(session: AsyncSession, order: Order) -> bool:
    """Storno referral payout when order is refunded. Idempotent."""
    earning = (
        await session.execute(
            select(ReferralEarnings).where(ReferralEarnings.order_id == order.id)
        )
    ).scalar_one_or_none()
    if earning is None:
        return False

    referrer = (
        await session.execute(
            select(User).where(User.telegram_id == earning.referrer_id).with_for_update()
        )
    ).scalar_one_or_none()
    if referrer is not None:
        referrer.balance -= earning.amount

    await session.delete(earning)
    order.referral_amount_cents = 0
    safe_create_task(invalidate_user_cache(earning.referrer_id))
    return True
