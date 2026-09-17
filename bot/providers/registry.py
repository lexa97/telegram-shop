"""Provider code → implementation."""

import json
from typing import Any

from bot.providers.fake import FakeProvider
from bot.providers.protocol import DigitalGoodsProvider
from bot.providers.wizard import WizardProvider

_REGISTRY: dict[str, type] = {
    "fake": FakeProvider,
    "wizard": WizardProvider,
}


def parse_provider_config(config_json: str) -> dict[str, Any]:
    try:
        return json.loads(config_json or "{}")
    except json.JSONDecodeError:
        return {}


def build_provider(code: str, config_json: str, *, fake_mode: str | None = None) -> DigitalGoodsProvider:
    cfg = parse_provider_config(config_json)
    if code == "fake":
        return FakeProvider(mode=fake_mode or cfg.get("mode", "success"))
    cls = _REGISTRY.get(code)
    if cls is None:
        raise ValueError(f"unknown_fulfillment_provider:{code}")
    return cls(cfg)
