"""Seed and read payment instruments (tests + dev)."""

import json

from sqlalchemy import select

from bot.database import Database
from bot.database.models.payment_config import PaymentGateway, PaymentInstrument
from bot.payments.gateway_settings import default_config_json


async def seed_default_payment_config() -> None:
    """Idempotent seed for gateways/instruments (pytest + fresh DB). Credentials live in admin UI."""
    async with Database().session() as s:
        existing = (await s.execute(select(PaymentGateway.id).limit(1))).scalar()
        if existing:
            return

        gateway_specs = [
            ("platega", True),
            ("cryptopay", True),
            ("stars", True),
            ("telegram_fiat", True),
            ("heleket", False),
        ]
        gateways = [
            PaymentGateway(
                code=code,
                enabled=enabled,
                config_json=default_config_json(code),
            )
            for code, enabled in gateway_specs
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
                    enabled=False,
                    sort_order=20,
                    currency="RUB",
                    gateway_id=by_code["cryptopay"],
                ),
                PaymentInstrument(
                    code="stars",
                    title="Telegram Stars",
                    enabled=False,
                    sort_order=30,
                    currency="RUB",
                    gateway_id=by_code["stars"],
                ),
                PaymentInstrument(
                    code="telegram_fiat",
                    title="Telegram Payments",
                    enabled=False,
                    sort_order=40,
                    currency="RUB",
                    gateway_id=by_code["telegram_fiat"],
                ),
            ]
        )


async def seed_test_payment_credentials() -> None:
    """Pytest: enable gateways with fake credentials (no env)."""
    async with Database().session() as s:
        platega = (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == "platega"))
        ).scalar_one()
        platega.config_json = json.dumps(
            {
                "merchant_id": "test-merchant",
                "api_secret": "test-secret",
                "payment_method": 11,
                "base_url": "https://app.platega.io",
                "return_url": "https://t.me",
                "failed_url": "https://t.me",
            }
        )
        platega.enabled = True

        cryptopay = (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == "cryptopay"))
        ).scalar_one()
        cryptopay.config_json = json.dumps({"api_token": "test_token"})
        cryptopay.enabled = True

        stars = (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == "stars"))
        ).scalar_one()
        stars.config_json = json.dumps({"stars_per_value": 0.91})
        stars.enabled = True

        fiat = (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == "telegram_fiat"))
        ).scalar_one()
        fiat.config_json = json.dumps({"provider_token": "test_provider"})
        fiat.enabled = True

        for inst in (await s.execute(select(PaymentInstrument))).scalars().all():
            inst.enabled = True
