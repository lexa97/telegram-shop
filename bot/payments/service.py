"""Orchestration: instruments list, create top-up, finalize from webhook."""

import json
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database import Database
from bot.database.methods.create import create_pending_payment
from bot.database.models.payment_config import PaymentGateway, PaymentInstrument
from bot.payments.credit import process_payment_topup
from bot.payments.gateways import platega as platega_gw
from bot.payments.types import CreatedPayment


async def list_enabled_instruments() -> list[PaymentInstrument]:
    async with Database().session() as s:
        rows = (
            await s.execute(
                select(PaymentInstrument)
                .join(PaymentGateway, PaymentGateway.id == PaymentInstrument.gateway_id)
                .where(
                    PaymentInstrument.enabled.is_(True),
                    PaymentGateway.enabled.is_(True),
                    PaymentInstrument.currency == "RUB",
                )
                .options(selectinload(PaymentInstrument.gateway))
                .order_by(PaymentInstrument.sort_order, PaymentInstrument.id)
            )
        ).scalars().all()
        return list(rows)


async def get_instrument_by_code(code: str) -> Optional[PaymentInstrument]:
    async with Database().session() as s:
        return (
            await s.execute(
                select(PaymentInstrument)
                .where(PaymentInstrument.code == code)
                .options(selectinload(PaymentInstrument.gateway))
            )
        ).scalars().first()


async def any_instrument_enabled() -> bool:
    return bool(await list_enabled_instruments())


async def create_topup_via_instrument(
    *,
    instrument: PaymentInstrument,
    user_id: int,
    amount_cents: int,
    username: str | None = None,
) -> CreatedPayment:
    gateway = instrument.gateway
    if not gateway.enabled or not instrument.enabled:
        raise ValueError("instrument_disabled")

    code = gateway.code
    if code == "platega":
        internal_uuid = str(uuid.uuid4())
        cfg = platega_gw.gateway_config_from_json(gateway.config_json)
        created = await platega_gw.create_payment(
            gateway_config=cfg,
            user_id=user_id,
            amount_cents=amount_cents,
            internal_uuid=internal_uuid,
            description="Пополнение баланса",
            username=username,
        )
        await create_pending_payment(
            provider=created.provider,
            external_id=created.external_id,
            user_id=user_id,
            amount=amount_cents,
            currency=instrument.currency,
            internal_uuid=internal_uuid,
        )
        return created

    if code == "heleket":
        raise ValueError("gateway_not_implemented")

    raise ValueError(f"unsupported_gateway:{code}")


async def finalize_platega_webhook(
    gateway_config: dict,
    body: dict,
    merchant_header: str | None,
    secret_header: str | None,
) -> tuple[int, str]:
    if not platega_gw.verify_webhook_headers(gateway_config, merchant_header, secret_header):
        return 401, "unauthorized"

    event = platega_gw.parse_webhook_body(body)
    if event.status != "CONFIRMED":
        return 200, "ignored"

    from bot.database.models import Payments

    async with Database().session() as s:
        payment = (
            await s.execute(
                select(Payments).where(
                    Payments.provider == "platega",
                    Payments.external_id == event.external_id,
                )
            )
        ).scalars().first()

    if not payment or not payment.user_id:
        return 404, "payment_not_found"

    ok, msg = await process_payment_topup(
        user_id=payment.user_id,
        amount=payment.amount,
        provider="platega",
        external_id=event.external_id,
    )
    if not ok and msg != "already_processed":
        return 500, msg
    return 200, "ok"
