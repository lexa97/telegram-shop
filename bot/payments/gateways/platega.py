"""Platega.io gateway adapter (https://docs.platega.io/)."""

import json
import logging
from decimal import Decimal
from typing import Any

import aiohttp

from bot.money import cents_to_float_rub
from bot.payments.types import CreatedPayment, PaymentStatusInfo, WebhookEvent

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://app.platega.io"


class PlategaError(Exception):
    pass


def _config(gateway_config: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "base_url": DEFAULT_BASE_URL.rstrip("/"),
        "payment_method": 11,
        "return_url": "https://t.me",
        "failed_url": "https://t.me",
    }
    merged.update(gateway_config or {})
    return merged


def _auth_headers(cfg: dict[str, Any]) -> dict[str, str]:
    merchant = (cfg.get("merchant_id") or "").strip()
    secret = (cfg.get("api_secret") or "").strip()
    if not merchant or not secret:
        raise PlategaError("platega_not_configured")
    return {"X-MerchantId": merchant, "X-Secret": secret, "Content-Type": "application/json"}


def verify_webhook_headers(
    gateway_config: dict[str, Any],
    merchant_header: str | None,
    secret_header: str | None,
) -> bool:
    cfg = _config(gateway_config)
    expected_m = (cfg.get("merchant_id") or "").strip()
    expected_s = (cfg.get("api_secret") or "").strip()
    if not expected_m or not expected_s:
        return False
    return merchant_header == expected_m and secret_header == expected_s


async def create_payment(
    *,
    gateway_config: dict[str, Any],
    user_id: int,
    amount_cents: int,
    internal_uuid: str,
    description: str,
    username: str | None = None,
) -> CreatedPayment:
    cfg = _config(gateway_config)
    headers = _auth_headers(cfg)
    amount_rub = float(cents_to_float_rub(amount_cents))
    body = {
        "paymentMethod": int(cfg.get("payment_method", 11)),
        "paymentDetails": {"amount": amount_rub, "currency": "RUB"},
        "description": description,
        "return": cfg.get("return_url"),
        "failedUrl": cfg.get("failed_url"),
        "payload": internal_uuid,
        "orderId": internal_uuid,
        "metadata": {
            "userId": str(user_id),
            "userName": username or str(user_id),
        },
    }
    url = f"{cfg['base_url']}/transaction/process"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=body) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                logger.warning("Platega create_payment HTTP %s: %s", resp.status, data)
                raise PlategaError(f"platega_http_{resp.status}")
    tx_id = data.get("transactionId") or data.get("transaction_id")
    redirect = data.get("redirect") or data.get("url")
    if not tx_id or not redirect:
        raise PlategaError("platega_invalid_response")
    return CreatedPayment(
        provider="platega",
        external_id=str(tx_id),
        payment_url=str(redirect),
        internal_uuid=internal_uuid,
        mode="redirect",
    )


async def fetch_status(gateway_config: dict[str, Any], external_id: str) -> PaymentStatusInfo:
    cfg = _config(gateway_config)
    headers = _auth_headers(cfg)
    url = f"{cfg['base_url']}/transaction/{external_id}"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status == 404:
                return PaymentStatusInfo(external_id=external_id, status="NOT_FOUND", paid=False)
            if resp.status >= 400:
                raise PlategaError(f"platega_http_{resp.status}")
    status = str(data.get("status", "")).upper()
    paid = status == "CONFIRMED"
    return PaymentStatusInfo(external_id=external_id, status=status, paid=paid)


def parse_webhook_body(body: dict[str, Any]) -> WebhookEvent:
    ext_id = str(body.get("id") or "")
    status = str(body.get("status", "")).upper()
    return WebhookEvent(provider="platega", external_id=ext_id, status=status, raw=body)


def gateway_config_from_json(config_json: str) -> dict[str, Any]:
    try:
        return json.loads(config_json or "{}")
    except json.JSONDecodeError:
        return {}
