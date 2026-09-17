"""Read payment gateway credentials from DB (ТЗ-04); not from env."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database import Database
from bot.database.models.payment_config import PaymentGateway

# JSON keys edited in SQLAdmin → Payment Gateways → config_json
GATEWAY_CONFIG_SCHEMAS: dict[str, dict[str, Any]] = {
    "platega": {
        "merchant_id": "string — ID мерчанта Platega",
        "api_secret": "string — секрет API / webhook (X-Secret)",
        "base_url": "https://app.platega.io",
        "payment_method": 11,
        "return_url": "https://t.me",
        "failed_url": "https://t.me",
        "webhook_path": "/webhooks/platega (на порту ADMIN_PORT, HTTPS)",
    },
    "cryptopay": {
        "api_token": "string — Crypto Pay API token",
    },
    "telegram_fiat": {
        "provider_token": "string — Telegram Payments provider token",
    },
    "stars": {
        "stars_per_value": "float — курс: звёзд за 1 ₽ (0 отключает)",
    },
    "heleket": {},
}


def default_config_json(code: str) -> str:
    schema = GATEWAY_CONFIG_SCHEMAS.get(code, {})
    obj: dict[str, Any] = {}
    for key, hint in schema.items():
        if key == "webhook_path":
            continue
        if isinstance(hint, (int, float)):
            obj[key] = hint
        elif isinstance(hint, str) and not hint.startswith("string"):
            obj[key] = hint
    return json.dumps(obj, ensure_ascii=False)


def _load_cfg(gateway: PaymentGateway) -> dict[str, Any]:
    try:
        data = json.loads(gateway.config_json or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def gateway_is_configured(gateway: PaymentGateway) -> bool:
    code = gateway.code
    cfg = _load_cfg(gateway)
    if code == "platega":
        return bool((cfg.get("merchant_id") or "").strip() and (cfg.get("api_secret") or "").strip())
    if code == "cryptopay":
        return bool((cfg.get("api_token") or "").strip())
    if code == "telegram_fiat":
        return bool((cfg.get("provider_token") or "").strip())
    if code == "stars":
        try:
            return float(cfg.get("stars_per_value", 0) or 0) > 0
        except (TypeError, ValueError):
            return False
    if code == "heleket":
        return False
    return bool(cfg)


def cryptopay_api_token(gateway: PaymentGateway) -> Optional[str]:
    token = (_load_cfg(gateway).get("api_token") or "").strip()
    return token or None


def telegram_provider_token(gateway: PaymentGateway) -> Optional[str]:
    token = (_load_cfg(gateway).get("provider_token") or "").strip()
    return token or None


def stars_per_value(gateway: PaymentGateway) -> float:
    try:
        return float(_load_cfg(gateway).get("stars_per_value") or 0)
    except (TypeError, ValueError):
        return 0.0


async def get_gateway_by_code(code: str) -> Optional[PaymentGateway]:
    async with Database().session() as s:
        return (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == code))
        ).scalars().first()


async def get_configured_gateway(code: str) -> Optional[PaymentGateway]:
    gw = await get_gateway_by_code(code)
    if not gw or not gw.enabled or not gateway_is_configured(gw):
        return None
    return gw
