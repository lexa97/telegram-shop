"""Map provider JSON to deliverable string using link result_mapping."""

from typing import Any


def extract_delivery_value(data: dict[str, Any], mapping: dict[str, Any]) -> str | None:
    """``mapping`` example: ``{"path": "delivery.value"}`` or ``{"path": "items.0.code"}``."""
    path = mapping.get("path") or "delivery.value"
    parts = path.split(".")
    cur: Any = data
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            return None
    if cur is None:
        return None
    return str(cur)
