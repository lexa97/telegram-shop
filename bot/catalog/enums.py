"""Catalog enums. All money fields elsewhere use kopecks (bot/money.py)."""


class FulfillmentType:
    STOCK = "STOCK"
    API = "API"
    ALL = frozenset({STOCK, API})


class StockUnitStatus:
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    ALL = frozenset({AVAILABLE, RESERVED, SOLD})
