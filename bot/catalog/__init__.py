"""Catalog and stock domain (ТЗ-03). No HTTP — DB and purchase flows only."""

from bot.catalog.enums import FulfillmentType, StockUnitStatus
from bot.catalog.stock import (
    StockAllocationError,
    assert_gift_purchase_allowed,
    consume_stock_units,
    release_stock_reservations,
    reserve_stock_units,
)

__all__ = [
    "FulfillmentType",
    "StockUnitStatus",
    "StockAllocationError",
    "assert_gift_purchase_allowed",
    "consume_stock_units",
    "reserve_stock_units",
    "release_stock_reservations",
]
