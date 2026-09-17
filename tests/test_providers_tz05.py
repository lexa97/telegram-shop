"""ТЗ-05: fulfillment providers, fake, wizard mock."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database.main import Database
from bot.database.methods.orders import create_order_with_snapshot
from bot.database.models.fulfillment_providers import FulfillmentProvider, GoodsProviderLink
from bot.database.models.orders import DeliveryType, Order
from bot.providers.admin_validate import validate_provider_link
from bot.providers.errors import ProviderFatalError, ProviderRetryableError
from bot.providers.fake import FakeProvider
from bot.providers.fulfillment import create_external_order
from bot.providers.links import select_primary_link
from bot.providers.registry import build_provider
from bot.providers.types import ProviderOrderRequest
from bot.providers.wizard import WizardProvider
from decimal import Decimal


@pytest.mark.asyncio
class TestFakeProvider:
    async def test_idempotent_create_order(self):
        p = FakeProvider()
        p.seed_product("prod-1")
        req = ProviderOrderRequest(
            external_product_id="prod-1",
            quantity=1,
            idempotency_key="order-42",
        )
        o1 = await p.create_order(req)
        o2 = await p.create_order(req)
        assert o1.external_order_id == o2.external_order_id

    async def test_timeout_is_retryable(self):
        p = FakeProvider(mode="timeout")
        p.seed_product("x")
        with pytest.raises(ProviderRetryableError):
            await p.create_order(
                ProviderOrderRequest("x", 1, idempotency_key="k1"),
            )

    async def test_out_of_stock_is_fatal(self):
        p = FakeProvider(mode="fatal")
        p.seed_product("x")
        with pytest.raises(ProviderFatalError) as exc:
            await p.create_order(
                ProviderOrderRequest("x", 1, idempotency_key="k2"),
            )
        assert exc.value.status_code == 400


@pytest.mark.asyncio
class TestWizardProvider:
    async def test_create_and_status_mocked(self):
        provider = WizardProvider(
            {
                "base_url": "https://api.wizard-bot.com/v1",
                "api_key": "k",
            }
        )
        def _http_response(body: dict):
            resp = MagicMock()
            resp.status = 200
            resp.text = AsyncMock(return_value=json.dumps(body))
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=resp)
            cm.__aexit__ = AsyncMock(return_value=None)
            return cm

        mock_session = MagicMock()
        mock_session.request = MagicMock(
            side_effect=[
                _http_response(
                    {
                        "status": 201,
                        "data": {
                            "id": 123456,
                            "status": "in_queue",
                            "category": "stars",
                            "recipient": "testuser",
                            "quantity": 100,
                        },
                    }
                ),
                _http_response(
                    {
                        "status": 200,
                        "data": {
                            "id": 123456,
                            "status": "success",
                            "category": "stars",
                            "recipient": "testuser",
                            "quantity": 100,
                        },
                    }
                ),
            ]
        )
        mock_sess_cm = MagicMock()
        mock_sess_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sess_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("bot.providers.wizard.aiohttp.ClientSession", return_value=mock_sess_cm):
            created = await provider.create_order(
                ProviderOrderRequest(
                    "stars",
                    100,
                    idempotency_key="99",
                    request_params={"recipient": "testuser"},
                )
            )
            assert created.external_order_id == "123456"
            assert created.delivery_value is None
            st = await provider.get_order_status("123456")
            assert st.completed
            assert st.delivery_value == "stars:100→@testuser"


@pytest.mark.asyncio
class TestFulfillmentService:
    async def test_create_external_order_idempotent(
        self, user_factory, category_factory, item_factory
    ):
        await user_factory(telegram_id=900001, balance=0)
        await category_factory("P")
        await item_factory(name="ApiItem", price=10, values=[])

        async with Database().session() as s:
            from bot.database.models import Goods

            goods = (await s.execute(select(Goods).where(Goods.name == "ApiItem"))).scalar_one()
            goods.fulfillment_type = "API"
            fake_prov = (
                await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
            ).scalar_one()
            link = GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake_prov.id,
                external_product_id="ext-prod",
                cost_cents=500,
                enabled=True,
                priority=1,
            )
            s.add(link)
            await s.flush()
            order = await create_order_with_snapshot(
                s,
                user_id=900001,
                goods_id=goods.id,
                quantity=1,
                unit_price_rub=Decimal("10"),
                delivery_type=DeliveryType.API,
            )
            await s.refresh(link, attribute_names=["provider"])
            r1 = await create_external_order(s, order, link)
            ext_id = order.provider_external_order_id
            r2 = await create_external_order(s, order, link)
            assert ext_id
            assert r1.external_order_id == r2.external_order_id
            assert order.fulfillment_payload
            assert "Authorization" not in (order.fulfillment_payload or "")

    async def test_select_primary_link_priority(self, category_factory, item_factory):
        await category_factory("P2")
        await item_factory(name="G2", price=1, values=[])

        async with Database().session() as s:
            from bot.database.models import Goods

            goods = (await s.execute(select(Goods).where(Goods.name == "G2"))).scalar_one()
            fake = (
                await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
            ).scalar_one()
            s.add_all(
                [
                    GoodsProviderLink(
                        goods_id=goods.id,
                        provider_id=fake.id,
                        external_product_id="low",
                        priority=50,
                        enabled=True,
                    ),
                    GoodsProviderLink(
                        goods_id=goods.id,
                        provider_id=fake.id,
                        external_product_id="high",
                        priority=10,
                        enabled=True,
                    ),
                ]
            )

        link = await select_primary_link(goods.id)
        assert link.external_product_id == "high"

    async def test_validate_link_fake(self, category_factory, item_factory):
        await category_factory("P3")
        await item_factory(name="G3", price=1, values=[])

        async with Database().session() as s:
            from bot.database.models import Goods

            goods = (await s.execute(select(Goods).where(Goods.name == "G3"))).scalar_one()
            fake = (
                await s.execute(select(FulfillmentProvider).where(FulfillmentProvider.code == "fake"))
            ).scalar_one()
            link = GoodsProviderLink(
                goods_id=goods.id,
                provider_id=fake.id,
                external_product_id="v-prod",
                enabled=True,
            )
            s.add(link)
            await s.flush()
            impl = build_provider("fake", '{"mode":"success"}')
            impl.seed_product("v-prod")
            ok, msg = await validate_provider_link(link, fake)
        assert ok is True
