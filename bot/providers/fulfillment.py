"""Create external provider orders (idempotent by order id)."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.fulfillment_providers import FulfillmentProvider, GoodsProviderLink
from bot.database.models.orders import Order
from bot.providers.mapping import extract_delivery_value
from bot.providers.registry import build_provider
from bot.providers.types import ProviderOrder, ProviderOrderRequest


def _merge_mapping(link: GoodsProviderLink, provider: FulfillmentProvider) -> dict:
    link_map = {}
    try:
        link_map = json.loads(link.result_mapping or "{}")
    except json.JSONDecodeError:
        pass
    if link_map:
        return link_map
    cfg = json.loads(provider.config_json or "{}")
    return cfg.get("result_mapping") or {"path": "delivery.value"}


async def create_external_order(
    session: AsyncSession,
    order: Order,
    link: GoodsProviderLink,
) -> ProviderOrder:
    """Call provider create_order once; reuse external id on retry."""
    if order.provider_external_order_id:
        if order.fulfillment_payload:
            return ProviderOrder(
                external_order_id=order.provider_external_order_id,
                status="COMPLETED",
                delivery_value=order.fulfillment_payload,
            )
        provider_row = link.provider
        impl = build_provider(provider_row.code, provider_row.config_json)
        return await impl.get_order_status(order.provider_external_order_id)

    provider_row: FulfillmentProvider = link.provider
    impl = build_provider(provider_row.code, provider_row.config_json)

    params = {}
    try:
        params = json.loads(link.request_params or "{}")
    except json.JSONDecodeError:
        params = {}

    mapping = _merge_mapping(link, provider_row)
    cfg = json.loads(provider_row.config_json or "{}")
    if mapping and provider_row.code == "wizard":
        cfg = {**cfg, "result_mapping": mapping}
        impl = build_provider(provider_row.code, json.dumps(cfg))

    request = ProviderOrderRequest(
        external_product_id=link.external_product_id,
        quantity=order.quantity,
        idempotency_key=str(order.id),
        request_params=params,
        cost_cents=link.cost_cents,
    )
    result = await impl.create_order(request)

    order.provider_id = provider_row.id
    order.provider_external_order_id = result.external_order_id
    if link.cost_cents and not order.cost_cents:
        order.cost_cents = link.cost_cents

    delivery = result.delivery_value
    if not delivery and result.raw:
        delivery = extract_delivery_value(result.raw, mapping)
    if delivery:
        order.fulfillment_payload = delivery

    return result
