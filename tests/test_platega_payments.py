"""ТЗ-04: Platega gateway, webhook, instruments."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from bot.database.main import Database
from bot.database.methods.create import create_pending_payment
from bot.database.models import Payments, User
from bot.database.models.payment_config import PaymentGateway, PaymentInstrument
from bot.money import rub_to_cents
from bot.payments.credit import process_payment_topup
from bot.payments.gateways.platega import (
    create_payment,
    parse_webhook_body,
    verify_webhook_headers,
)
from bot.payments.service import finalize_platega_webhook, list_enabled_instruments
from bot.web.payment_webhooks import platega_webhook


@pytest.mark.asyncio
class TestPlategaGateway:
    async def test_create_payment_returns_url(self):
        cfg = {
            "merchant_id": "m-1",
            "api_secret": "s-1",
            "base_url": "https://app.platega.io",
            "payment_method": 11,
            "return_url": "https://t.me",
            "failed_url": "https://t.me",
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "transactionId": "tx-uuid-1",
                "redirect": "https://pay.platega.io/?id=1",
                "status": "PENDING",
            }
        )
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_resp
        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_cm)
        mock_sess_cm = AsyncMock()
        mock_sess_cm.__aenter__.return_value = mock_session

        with patch("bot.payments.gateways.platega.aiohttp.ClientSession", return_value=mock_sess_cm):
            created = await create_payment(
                gateway_config=cfg,
                user_id=700001,
                amount_cents=rub_to_cents(100),
                internal_uuid="internal-uuid-1",
                description="topup",
            )
        assert created.payment_url.startswith("https://pay.platega.io")
        assert created.external_id == "tx-uuid-1"
        assert created.provider == "platega"

    def test_webhook_signature(self):
        cfg = {"merchant_id": "m-1", "api_secret": "s-1"}
        assert verify_webhook_headers(cfg, "m-1", "s-1") is True
        assert verify_webhook_headers(cfg, "bad", "s-1") is False

    async def test_webhook_credits_balance_once(self, user_factory):
        await user_factory(telegram_id=700010, balance=0)
        await create_pending_payment(
            "platega", "tx-wh-1", 700010, rub_to_cents(250), "RUB", internal_uuid="u-1"
        )
        body = {"id": "tx-wh-1", "status": "CONFIRMED", "amount": 250, "currency": "RUB"}
        cfg = {"merchant_id": "m-1", "api_secret": "s-1"}

        status1, _ = await finalize_platega_webhook(cfg, body, "m-1", "s-1")
        status2, _ = await finalize_platega_webhook(cfg, body, "m-1", "s-1")
        assert status1 == 200
        assert status2 == 200

        async with Database().session() as s:
            user = (await s.execute(select(User).where(User.telegram_id == 700010))).scalar_one()
            assert user.balance == rub_to_cents(250)

    async def test_webhook_rejects_bad_secret(self, user_factory):
        await user_factory(telegram_id=700011, balance=0)
        await create_pending_payment("platega", "tx-wh-2", 700011, 10000, "RUB")
        body = {"id": "tx-wh-2", "status": "CONFIRMED"}
        cfg = {"merchant_id": "m-1", "api_secret": "s-1"}
        status, _ = await finalize_platega_webhook(cfg, body, "m-1", "wrong")
        assert status == 401

    async def test_disabled_instrument_not_listed(self):
        async with Database().session() as s:
            inst = (
                await s.execute(select(PaymentInstrument).where(PaymentInstrument.code == "card_mir"))
            ).scalar_one()
            inst.enabled = False
        listed = await list_enabled_instruments()
        assert all(i.code != "card_mir" for i in listed)

    async def test_process_payment_topup_idempotent(self, user_factory):
        await user_factory(telegram_id=700012, balance=0)
        ok1, _ = await process_payment_topup(700012, 5000, "platega", "ext-1")
        ok2, msg = await process_payment_topup(700012, 5000, "platega", "ext-1")
        assert ok1 is True
        assert ok2 is False
        assert msg == "already_processed"
        async with Database().session() as s:
            user = (await s.execute(select(User).where(User.telegram_id == 700012))).scalar_one()
            assert user.balance == 5000

    async def test_platega_webhook_route(self, user_factory):
        await user_factory(telegram_id=700013, balance=0)
        await create_pending_payment("platega", "tx-route", 700013, 3000, "RUB")
        request = MagicMock()
        request.json = AsyncMock(
            return_value={"id": "tx-route", "status": "CONFIRMED", "currency": "RUB", "amount": 30}
        )
        request.headers = MagicMock()
        request.headers.get = lambda k, d=None: {"X-MerchantId": "test-merchant", "X-Secret": "test-secret"}.get(k, d)

        response = await platega_webhook(request)
        assert response.status_code == 200

    def test_parse_webhook_body(self):
        ev = parse_webhook_body({"id": "abc", "status": "CONFIRMED"})
        assert ev.external_id == "abc"
        assert ev.status == "CONFIRMED"
