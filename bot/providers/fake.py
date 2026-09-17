"""In-memory provider for pytest (success / timeout / fatal / idempotency)."""

from __future__ import annotations

import asyncio
from typing import Any

from bot.providers.errors import ProviderFatalError, ProviderRetryableError
from bot.providers.types import ProviderOrder, ProviderOrderRequest, ProviderProduct


class FakeProvider:
    """Configurable fake fulfillment provider."""

    def __init__(self, mode: str = "success"):
        self.mode = mode
        self._products: dict[str, ProviderProduct] = {}
        self._orders_by_id: dict[str, ProviderOrder] = {}
        self._idempotency: dict[str, str] = {}

    def seed_product(self, external_product_id: str, title: str = "Fake", available: bool = True) -> None:
        self._products[external_product_id] = ProviderProduct(
            external_product_id=external_product_id,
            title=title,
            available=available,
            raw={"id": external_product_id},
        )

    async def get_product(self, external_product_id: str) -> ProviderProduct:
        if external_product_id not in self._products:
            if self.mode == "success":
                self.seed_product(external_product_id)
            else:
                raise ProviderFatalError("product_not_found", status_code=404)
        return self._products[external_product_id]

    async def create_order(self, request: ProviderOrderRequest) -> ProviderOrder:
        if self.mode == "timeout":
            raise ProviderRetryableError("timeout", status_code=504)
        if self.mode == "fatal":
            raise ProviderFatalError("out_of_stock", status_code=400)
        if self.mode == "unavailable_product":
            raise ProviderFatalError("product_unavailable", status_code=404)

        existing = self._idempotency.get(request.idempotency_key)
        if existing:
            return self._orders_by_id[existing]

        if request.external_product_id not in self._products and self.mode == "success":
            self.seed_product(request.external_product_id)
        product = self._products.get(request.external_product_id)
        if not product or not product.available:
            raise ProviderFatalError("out_of_stock", status_code=400)

        external_id = f"fake-{len(self._orders_by_id) + 1}"
        order = ProviderOrder(
            external_order_id=external_id,
            status="COMPLETED",
            delivery_value=f"KEY-{request.external_product_id}-{request.quantity}",
            raw={"id": external_id, "status": "completed"},
        )
        self._orders_by_id[external_id] = order
        self._idempotency[request.idempotency_key] = external_id
        if self.mode == "slow":
            await asyncio.sleep(0)
        return order

    async def get_order_status(self, external_order_id: str) -> ProviderOrder:
        order = self._orders_by_id.get(external_order_id)
        if not order:
            raise ProviderFatalError("order_not_found", status_code=404)
        return order

    async def cancel_order(self, external_order_id: str) -> None:
        order = self._orders_by_id.get(external_order_id)
        if order:
            self._orders_by_id[external_order_id] = ProviderOrder(
                external_order_id=order.external_order_id,
                status="CANCELED",
                delivery_value=order.delivery_value,
                raw={**order.raw, "status": "canceled"},
            )
