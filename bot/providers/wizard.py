"""Wizard Bot reseller API (https://api.wizard-bot.com/docs/).

Base URL: https://api.wizard-bot.com/v1
Auth: header X-API-KEY

Orders (Telegram Stars / Premium):
  POST /orders/create   — body: recipient, quantity, category (stars|premium)
  GET  /orders/get/{order_id}
  GET  /orders/history

Account:
  GET  /user/profile
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from bot.providers.errors import ProviderFatalError, ProviderRetryableError
from bot.providers.types import ProviderOrder, ProviderOrderRequest, ProviderProduct

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.wizard-bot.com/v1"
_WIZARD_CATEGORIES = frozenset({"stars", "premium"})
_TERMINAL_SUCCESS = frozenset({"success"})
_TERMINAL_FAILED = frozenset({"failed"})
_PENDING_STATUSES = frozenset({"in_queue", "pending", "processing"})


class WizardProvider:
    def __init__(self, config: dict[str, Any]):
        self._base_url = (config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        self._api_key = (config.get("api_key") or config.get("api_secret") or "").strip()
        self._timeout = float(config.get("timeout_seconds", 30))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["X-API-KEY"] = self._api_key
        return headers

    @staticmethod
    def _unwrap_payload(data: dict[str, Any]) -> dict[str, Any]:
        inner = data.get("data")
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return inner[0]
        return data

    def _classify_http_error(self, status: int, data: dict[str, Any]) -> Exception:
        if status in (408, 429, 500, 502, 503, 504):
            return ProviderRetryableError(f"wizard_http_{status}", status_code=status)
        if status == 402:
            return ProviderFatalError("wizard_insufficient_balance", status_code=402)
        detail = data.get("detail") or data.get("error") or data.get("message")
        msg = f"wizard_http_{status}"
        if detail:
            msg = f"{msg}:{detail}"
        return ProviderFatalError(msg, status_code=status)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise ProviderFatalError("wizard_api_key_required", status_code=401)

        url = f"{self._base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                    params=params,
                ) as resp:
                    text = await resp.text()
                    try:
                        data = json.loads(text) if text else {}
                    except json.JSONDecodeError:
                        data = {"raw": text}
                    if not isinstance(data, dict):
                        data = {"data": data}
                    if resp.status >= 400:
                        raise self._classify_http_error(resp.status, data)
                    return data
        except (asyncio.TimeoutError, TimeoutError):
            raise ProviderRetryableError("timeout", status_code=504)
        except aiohttp.ClientError as e:
            raise ProviderRetryableError(str(e))

    async def get_product(self, external_product_id: str) -> ProviderProduct:
        """``external_product_id`` = ``stars`` or ``premium`` (категория Wizard)."""
        category = (external_product_id or "").strip().lower()
        if category not in _WIZARD_CATEGORIES:
            raise ProviderFatalError(
                f"wizard_invalid_category:{external_product_id}", status_code=400
            )
        title = "Telegram Stars" if category == "stars" else "Telegram Premium"
        return ProviderProduct(
            external_product_id=category,
            title=title,
            available=True,
            raw={"category": category},
        )

    async def create_order(self, request: ProviderOrderRequest) -> ProviderOrder:
        category = (request.external_product_id or "").strip().lower()
        if category not in _WIZARD_CATEGORIES:
            raise ProviderFatalError("wizard_invalid_category", status_code=400)

        params = request.request_params or {}
        recipient = params.get("recipient") or params.get("username")
        if not recipient:
            raise ProviderFatalError("wizard_recipient_required", status_code=400)
        recipient = str(recipient).strip().lstrip("@")
        if len(recipient) < 4 or len(recipient) > 32:
            raise ProviderFatalError("wizard_invalid_recipient", status_code=400)

        quantity = int(request.quantity)
        if category == "premium" and quantity not in (3, 6, 12):
            raise ProviderFatalError("wizard_premium_quantity", status_code=400)
        if category == "stars" and (quantity < 50 or quantity > 1_000_000):
            raise ProviderFatalError("wizard_stars_quantity", status_code=400)

        body = {
            "recipient": recipient,
            "quantity": quantity,
            "category": category,
        }
        data = await self._request("POST", "/orders/create", json_body=body)
        return self._order_from_response(self._unwrap_payload(data), recipient_hint=recipient)

    async def get_order_status(self, external_order_id: str) -> ProviderOrder:
        data = await self._request("GET", f"/orders/get/{external_order_id}")
        return self._order_from_response(self._unwrap_payload(data))

    async def cancel_order(self, external_order_id: str) -> None:
        raise ProviderFatalError("wizard_cancel_not_supported", status_code=405)

    def _delivery_from_order(self, data: dict[str, Any], recipient_hint: str | None = None) -> str | None:
        status = str(data.get("status") or "").lower()
        if status not in _TERMINAL_SUCCESS:
            return None
        category = data.get("category") or "stars"
        qty = data.get("quantity")
        recipient = data.get("recipient") or recipient_hint or "?"
        return f"{category}:{qty}→@{recipient}"

    def _order_from_response(
        self,
        data: dict[str, Any],
        *,
        recipient_hint: str | None = None,
    ) -> ProviderOrder:
        ext_id = data.get("id")
        if ext_id is None:
            raise ProviderFatalError("wizard_invalid_order_response")
        status = str(data.get("status") or "unknown").lower()
        delivery = self._delivery_from_order(data, recipient_hint)
        return ProviderOrder(
            external_order_id=str(ext_id),
            status=status,
            delivery_value=delivery,
            raw={k: v for k, v in data.items() if k.lower() not in ("authorization", "api_key")},
        )
