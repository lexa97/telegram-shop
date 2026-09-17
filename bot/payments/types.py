from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class CreatedPayment:
    provider: str
    external_id: str
    payment_url: Optional[str]
    internal_uuid: str
    mode: str = "redirect"  # redirect | telegram_invoice


@dataclass(frozen=True)
class WebhookEvent:
    provider: str
    external_id: str
    status: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class PaymentStatusInfo:
    external_id: str
    status: str
    paid: bool
