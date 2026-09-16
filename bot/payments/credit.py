"""Idempotent balance top-up without referral (ТЗ-04 / ТЗ-07)."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.database import Database
from bot.database.methods.read import invalidate_stats_cache, invalidate_user_cache
from bot.database.methods.cache_utils import safe_create_task
from bot.database.methods.audit import log_audit
from bot.database.models import Payments, User, Operations
from bot.misc import EnvKeys


class _Abort(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


async def process_payment_topup(
    user_id: int,
    amount: int,
    provider: str,
    external_id: str,
) -> tuple[bool, str]:
    """Credit user balance once per (provider, external_id). Amount in kopecks."""
    try:
        async with Database().session() as s:
            existing_payment = (
                await s.execute(
                    select(Payments)
                    .where(
                        Payments.provider == provider,
                        Payments.external_id == external_id,
                    )
                    .with_for_update()
                )
            ).scalars().first()

            if existing_payment:
                if existing_payment.status in ("succeeded", "paid", "completed"):
                    raise _Abort("already_processed")
                existing_payment.status = "succeeded"
                amount = existing_payment.amount
            else:
                s.add(
                    Payments(
                        provider=provider,
                        external_id=external_id,
                        user_id=user_id,
                        amount=amount,
                        currency=EnvKeys.PAY_CURRENCY,
                        status="succeeded",
                    )
                )

            user = (
                await s.execute(select(User).where(User.telegram_id == user_id).with_for_update())
            ).scalars().one()
            user.balance += amount
            s.add(
                Operations(
                    user_id=user_id,
                    operation_value=amount,
                    operation_time=datetime.now(timezone.utc),
                )
            )

    except _Abort as e:
        return False, e.code
    except IntegrityError:
        return False, "already_processed"
    except Exception as e:
        await log_audit(
            "payment_failed",
            level="WARNING",
            user_id=user_id,
            resource_type="Payment",
            details=f"provider={provider}, amount={amount}, error={e}",
        )
        return False, "payment_error"

    safe_create_task(invalidate_user_cache(user_id))
    safe_create_task(invalidate_stats_cache())
    return True, "success"
