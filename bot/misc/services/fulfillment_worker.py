"""Background fulfillment and order expiry (ТЗ-12)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database import Database
from bot.database.methods.orders import (
    expire_due_created_orders,
    list_processing_api_order_ids,
    transition_order,
)
from bot.database.models.orders import DeliveryType, Order, OrderStatus
from bot.misc.env import EnvKeys
from bot.misc.services.fulfillment import (
    FulfillTickResult,
    fulfill_processing_order_by_id,
    refund_failed_order,
)

logger = logging.getLogger(__name__)


class FulfillmentWorker:
    """Poll PROCESSING API orders, expire CREATED TTL orders, fail hung PROCESSING."""

    def __init__(self, bot):
        self.bot = bot
        self.tasks: list[asyncio.Task] = []
        self.running = False

    @staticmethod
    def _poll_interval() -> int:
        return int(EnvKeys._get_optional("FULFILLMENT_POLL_INTERVAL", "30"))

    @staticmethod
    def _batch_size() -> int:
        return int(EnvKeys._get_optional("FULFILLMENT_BATCH_SIZE", "10"))

    @staticmethod
    def _hung_seconds() -> int:
        return int(EnvKeys._get_optional("FULFILLMENT_HUNG_SECONDS", "3600"))

    @staticmethod
    def _expire_batch() -> int:
        return int(EnvKeys._get_optional("CREATED_EXPIRE_BATCH", "50"))

    async def start(self) -> None:
        logger.info("Starting fulfillment worker...")
        self.running = True
        interval = self._poll_interval()
        self.tasks.append(
            asyncio.create_task(self._run_periodically(self._tick, interval))
        )

    async def stop(self) -> None:
        self.running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Fulfillment worker stopped")

    async def _run_periodically(self, step, interval: int) -> None:
        while self.running:
            try:
                await step()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "Fulfillment worker step %s failed: %s",
                    getattr(step, "__name__", step),
                    e,
                    exc_info=True,
                )
                await asyncio.sleep(30)
                continue
            await asyncio.sleep(interval)

    async def _tick(self) -> None:
        expired = await self._expire_created()
        if expired:
            logger.info("Expired %s CREATED order(s)", expired)
        await self._fail_hung_processing()
        order_ids = await self._claim_processing_ids()
        for order_id in order_ids:
            result = await fulfill_processing_order_by_id(order_id)
            if result.status == "completed":
                await notify_order_delivery(self.bot, order_id)

    async def _expire_created(self) -> int:
        async with Database().session() as session:
            return await expire_due_created_orders(
                session, limit=self._expire_batch()
            )

    async def _claim_processing_ids(self) -> list[int]:
        async with Database().session() as session:
            return await list_processing_api_order_ids(
                session, limit=self._batch_size()
            )

    async def _fail_hung_processing(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._hung_seconds())
        async with Database().session() as session:
            stmt = (
                select(Order)
                .where(
                    Order.status == OrderStatus.PROCESSING,
                    Order.delivery_type == DeliveryType.API,
                    Order.processing_started_at.isnot(None),
                    Order.processing_started_at < cutoff,
                )
                .limit(self._batch_size())
            )
            from bot.catalog.stock import _use_skip_locked

            if _use_skip_locked(session):
                stmt = stmt.with_for_update(skip_locked=True)
            else:
                stmt = stmt.with_for_update()
            hung = (await session.execute(stmt)).scalars().all()
            for order in hung:
                logger.warning(
                    "Failing hung PROCESSING order id=%s age_seconds>%s",
                    order.id,
                    self._hung_seconds(),
                )
                await transition_order(
                    session, order, OrderStatus.FAILED, actor_id=order.user_id
                )
                await refund_failed_order(session, order, actor_id=order.user_id)


async def notify_order_delivery(bot, order_id: int) -> bool:
    """Send purchase value to buyer once (``delivery_notified_at`` guard)."""
    from bot.database.models.main import BoughtGoods, User
    from bot.i18n import localize
    from bot.money import cents_to_float_rub

    async with Database().session() as session:
        order = (
            await session.execute(
                select(Order)
                .where(Order.id == order_id)
                .options(selectinload(Order.goods))
            )
        ).scalar_one_or_none()
        if not order or order.status != OrderStatus.COMPLETED:
            return False
        if order.delivery_notified_at is not None:
            return False
        bg = (
            await session.execute(
                select(BoughtGoods).where(BoughtGoods.order_id == order.id).limit(1)
            )
        ).scalar_one_or_none()
        if not bg:
            return False
        recipient = int(order.gift_telegram_id or order.user_id)
        goods_name = order.goods.name
        value = bg.value
        user = (
            await session.execute(
                select(User).where(User.telegram_id == order.user_id)
            )
        ).scalar_one()

    try:
        await bot.send_message(
            recipient,
            localize(
                "shop.purchase.success",
                balance=cents_to_float_rub(user.balance),
                currency=EnvKeys.PAY_CURRENCY,
                value=value,
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(
            "Failed delivery notification order id=%s recipient=%s: %s",
            order_id,
            recipient,
            e,
        )
        return False

    async with Database().session() as session:
        order = (
            await session.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            )
        ).scalar_one_or_none()
        if not order or order.delivery_notified_at is not None:
            return True
        order.delivery_notified_at = datetime.now(timezone.utc)

    logger.info(
        "Delivery notified for order id=%s item=%s recipient=%s",
        order_id,
        goods_name,
        recipient,
    )
    return True


async def run_fulfillment_tick_for_tests() -> FulfillTickResult | None:
    """Single worker pass without sleeping (tests)."""
    worker = FulfillmentWorker(bot=None)
    await worker._expire_created()
    await worker._fail_hung_processing()
    ids = await worker._claim_processing_ids()
    last: FulfillTickResult | None = None
    for oid in ids:
        last = await fulfill_processing_order_by_id(oid)
    return last
