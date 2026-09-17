"""Payment gateway config from DB (ТЗ-04 admin UI)."""

import json

import pytest
from sqlalchemy import select

from bot.database import Database
from bot.database.models.payment_config import PaymentGateway
from bot.payments.gateway_settings import gateway_is_configured
from bot.payments.service import list_enabled_instruments


@pytest.mark.asyncio
async def test_list_instruments_requires_configured_gateway():
    instruments = await list_enabled_instruments()
    codes = {i.code for i in instruments}
    assert "card_mir" in codes

    async with Database().session() as s:
        platega = (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == "platega"))
        ).scalar_one()
        platega.config_json = json.dumps({"merchant_id": "", "api_secret": ""})

    instruments2 = await list_enabled_instruments()
    assert all(i.code != "card_mir" for i in instruments2)


@pytest.mark.asyncio
async def test_gateway_is_configured_platega():
    async with Database().session() as s:
        gw = (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == "platega"))
        ).scalar_one()
        assert gateway_is_configured(gw) is True
        gw.config_json = "{}"
        assert gateway_is_configured(gw) is False
