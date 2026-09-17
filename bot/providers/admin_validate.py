"""Admin-side validation of goods↔provider links (ТЗ-05 / ТЗ-10)."""

import json

from bot.providers.registry import build_provider
from bot.database.models.fulfillment_providers import FulfillmentProvider, GoodsProviderLink


async def validate_provider_link(link: GoodsProviderLink, provider: FulfillmentProvider) -> tuple[bool, str]:
    """
    Validate link via get_product when the provider supports catalog lookup.
    Returns (ok, message). Skips with ok=True if provider code is fake or catalog disabled in config.
    """
    cfg = json.loads(provider.config_json or "{}")
    if provider.code == "fake":
        impl = build_provider(provider.code, provider.config_json)
        await impl.get_product(link.external_product_id)
        return True, "ok"
    if cfg.get("skip_catalog_validation"):
        return True, "catalog_validation_skipped"
    impl = build_provider(provider.code, provider.config_json)
    try:
        product = await impl.get_product(link.external_product_id)
    except Exception as e:
        return False, str(e)
    if not product.available:
        return False, "product_not_available"
    return True, "ok"
