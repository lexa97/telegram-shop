"""Seed fulfillment providers for tests."""

import json

from sqlalchemy import select

from bot.database import Database
from bot.database.models.fulfillment_providers import FulfillmentProvider


async def seed_fulfillment_providers() -> None:
    async with Database().session() as s:
        if (await s.execute(select(FulfillmentProvider.id).limit(1))).scalar():
            return
        s.add_all(
            [
                FulfillmentProvider(
                    code="wizard",
                    name="Wizard",
                    enabled=True,
                    config_json=json.dumps(
                        {
                            "base_url": "https://api.wizard.example",
                            "api_key": "test-key",
                            "timeout_seconds": 5,
                            "result_mapping": {"path": "delivery.value"},
                        }
                    ),
                ),
                FulfillmentProvider(
                    code="fake",
                    name="Fake",
                    enabled=True,
                    config_json='{"mode":"success"}',
                ),
            ]
        )
