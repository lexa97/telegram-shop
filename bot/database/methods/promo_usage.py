"""Promo usage counting and recording (ТЗ-07)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import PromoCodeUsages, PromoCodes


class PromoUsageLimitError(Exception):
    """Promo cannot be redeemed (global or per-user cap)."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


async def count_promo_usages_for_user(
    session: AsyncSession, promo_id: int, user_id: int
) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(PromoCodeUsages)
            .where(
                PromoCodeUsages.promo_id == promo_id,
                PromoCodeUsages.user_id == user_id,
            )
        )
    ).scalar() or 0


async def record_promo_usage(
    session: AsyncSession,
    promo: PromoCodes,
    user_id: int,
    *,
    order_id: int | None = None,
) -> None:
    """Increment global counter and append usage row (caller holds promo row lock)."""
    if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
        raise PromoUsageLimitError("max_uses")

    max_per_user = int(getattr(promo, "max_uses_per_user", 1) or 1)
    usage_count = await count_promo_usages_for_user(session, promo.id, user_id)
    if usage_count >= max_per_user:
        raise PromoUsageLimitError("already_used")

    promo.current_uses += 1
    session.add(
        PromoCodeUsages(
            promo_id=promo.id,
            user_id=user_id,
            order_id=order_id,
        )
    )
