from typing import Protocol, runtime_checkable

from bot.providers.types import ProviderOrder, ProviderOrderRequest, ProviderProduct


@runtime_checkable
class DigitalGoodsProvider(Protocol):
    async def get_product(self, external_product_id: str) -> ProviderProduct: ...

    async def create_order(self, request: ProviderOrderRequest) -> ProviderOrder: ...

    async def get_order_status(self, external_order_id: str) -> ProviderOrder: ...

    async def cancel_order(self, external_order_id: str) -> None: ...
