"""Wizard reseller HTTP adapter.

API shape (documented in docs/MEMORY.md):
  GET  {base}/v1/products/{id}
  POST {base}/v1/orders       + Idempotency-Key header
  GET  {base}/v1/orders/{id}
  POST {base}/v1/orders/{id}/cancel
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from bot.providers.errors import ProviderFatalError, ProviderRetryableError
from bot.providers.mapping import extract_delivery_value
from bot.providers.types import ProviderOrder, ProviderOrderRequest, ProviderProduct

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.wizard.example"


class WizardProvider:
    def __init__(self, config: dict[str, Any]):
        self._base_url = (config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        self._api_key = (config.get("api_key") or "").strip()
        self._timeout = float(config.get("timeout_seconds", 30))
        self._result_mapping = config.get("result_mapping") or {"path": "delivery.value"}

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    url,
                    headers=self._headers(idempotency_key),
                    json=json_body,
                ) as resp:
                    text = await resp.text()
                    try:
                        data = json.loads(text) if text else {}
                    except json.JSONDecodeError:
                        data = {"raw": text}
                    if resp.status in (408, 429, 500, 502, 503, 504):
                        raise ProviderRetryableError(f"wizard_http_{resp.status}", status_code=resp.status)
                    if resp.status >= 400:
                        raise ProviderFatalError(f"wizard_http_{resp.status}", status_code=resp.status)
                    return data if isinstance(data, dict) else {"data": data}
        except (asyncio.TimeoutError, TimeoutError):
            raise ProviderRetryableError("timeout", status_code=504)
        except aiohttp.ClientError as e:
            raise ProviderRetryableError(str(e))

    async def get_product(self, external_product_id: str) -> ProviderProduct:
        data = await self._request("GET", f"/v1/products/{external_product_id}")
        title = str(data.get("name") or data.get("title") or external_product_id)
        available = bool(data.get("available", data.get("in_stock", True)))
        return ProviderProduct(
            external_product_id=external_product_id,
            title=title,
            available=available,
            raw=data,
        )

    async def create_order(self, request: ProviderOrderRequest) -> ProviderOrder:
        body = {
            "product_id": request.external_product_id,
            "quantity": request.quantity,
            **request.request_params,
        }
        data = await self._request(
            "POST",
            "/v1/orders",
            json_body=body,
            idempotency_key=request.idempotency_key,
        )
        return self._order_from_response(data)

    async def get_order_status(self, external_order_id: str) -> ProviderOrder:
        data = await self._request("GET", f"/v1/orders/{external_order_id}")
        return self._order_from_response(data)

    async def cancel_order(self, external_order_id: str) -> None:
        await self._request("POST", f"/v1/orders/{external_order_id}/cancel")

    def _order_from_response(self, data: dict[str, Any]) -> ProviderOrder:
        ext_id = str(data.get("id") or data.get("order_id") or data.get("orderId") or "")
        status = str(data.get("status") or "UNKNOWN")
        delivery = extract_delivery_value(data, self._result_mapping)
        if not ext_id:
            raise ProviderFatalError("wizard_invalid_order_response")
        return ProviderOrder(
            external_order_id=ext_id,
            status=status,
            delivery_value=delivery,
            raw={k: v for k, v in data.items() if k.lower() != "authorization"},
        )
