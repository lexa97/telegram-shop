"""Seed and read payment instruments (tests + dev)."""

import json
import os

from sqlalchemy import select

from bot.database import Database
from bot.database.models.payment_config import PaymentGateway, PaymentInstrument


async def seed_default_payment_config() -> None:
    """Idempotent seed for gateways/instruments (pytest + fresh DB)."""
    async with Database().session() as s:
        existing = (await s.execute(select(PaymentGateway.id).limit(1))).scalar()
        if existing:
            return

        platega_cfg = json.dumps(
            {
                "merchant_id": os.getenv("PLATEGA_MERCHANT_ID", "test-merchant"),
                "api_secret": os.getenv("PLATEGA_SECRET", "test-secret"),
                "payment_method": 11,
                "base_url": os.getenv("PLATEGA_BASE_URL", "https://app.platega.io"),
                "return_url": "https://t.me",
                "failed_url": "https://t.me",
            }
        )
        gateways = [
            PaymentGateway(code="platega", enabled=True, config_json=platega_cfg),
            PaymentGateway(code="cryptopay", enabled=True, config_json="{}"),
            PaymentGateway(code="stars", enabled=True, config_json="{}"),
            PaymentGateway(code="telegram_fiat", enabled=True, config_json="{}"),
            PaymentGateway(code="heleket", enabled=False, config_json="{}"),
        ]
        s.add_all(gateways)
        await s.flush()

        by_code = {g.code: g.id for g in gateways}
        s.add_all(
            [
                PaymentInstrument(
                    code="card_mir",
                    title="Карта / МИР",
                    enabled=True,
                    sort_order=10,
                    currency="RUB",
                    gateway_id=by_code["platega"],
                ),
                PaymentInstrument(
                    code="cryptopay",
                    title="CryptoPay",
                    enabled=bool(os.getenv("CRYPTO_PAY_TOKEN")),
                    sort_order=20,
                    currency="RUB",
                    gateway_id=by_code["cryptopay"],
                ),
                PaymentInstrument(
                    code="stars",
                    title="Telegram Stars",
                    enabled=float(os.getenv("STARS_PER_VALUE", "0.91") or 0) > 0,
                    sort_order=30,
                    currency="RUB",
                    gateway_id=by_code["stars"],
                ),
                PaymentInstrument(
                    code="telegram_fiat",
                    title="Telegram Payments",
                    enabled=bool(os.getenv("TELEGRAM_PROVIDER_TOKEN")),
                    sort_order=40,
                    currency="RUB",
                    gateway_id=by_code["telegram_fiat"],
                ),
            ]
        )
