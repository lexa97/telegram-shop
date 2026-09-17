"""DTOs for fulfillment providers (ТЗ-05). Amounts in kopecks unless noted."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ProviderProduct:
    external_product_id: str
    title: str
    available: bool
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderOrderRequest:
    external_product_id: str
    quantity: int
    idempotency_key: str
    request_params: dict[str, Any] = field(default_factory=dict)
    cost_cents: int = 0


@dataclass(frozen=True)
class ProviderOrder:
    external_order_id: str
    status: str
    delivery_value: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        return self.status.upper() in ("COMPLETED", "SUCCESS", "DELIVERED", "PAID")
