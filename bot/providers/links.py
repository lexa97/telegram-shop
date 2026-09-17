"""Resolve GoodsProviderLink for a product."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database import Database
from bot.database.models.fulfillment_providers import FulfillmentProvider, GoodsProviderLink


async def select_primary_link(goods_id: int) -> Optional[GoodsProviderLink]:
    """First enabled link by priority (fallback chain — ТЗ-06)."""
    async with Database().session() as s:
        return (
            await s.execute(
                select(GoodsProviderLink)
                .join(FulfillmentProvider, FulfillmentProvider.id == GoodsProviderLink.provider_id)
                .where(
                    GoodsProviderLink.goods_id == goods_id,
                    GoodsProviderLink.enabled.is_(True),
                    FulfillmentProvider.enabled.is_(True),
                )
                .options(selectinload(GoodsProviderLink.provider))
                .order_by(GoodsProviderLink.priority.asc(), GoodsProviderLink.id.asc())
                .limit(1)
            )
        ).scalars().first()
