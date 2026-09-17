"""Shared helpers for SQLAdmin (ТЗ-10)."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.orders import Order, OrderStatus
from bot.misc import EnvKeys
from bot.money import format_cents_for_ui


def web_panel_operator_id() -> int:
    """Telegram user id recorded in audit for web-initiated staff actions."""
    try:
        return int(EnvKeys.ADMIN_WEB_OPERATOR_ID)
    except (TypeError, ValueError):
        return 0


def mask_gateway_config(model: Any, _name: str) -> str:
    if EnvKeys.admin_panel_operator_mode():
        return "••••••••"
    raw = getattr(model, "config_json", None) or ""
    if len(raw) <= 80:
        return raw
    return raw[:77] + "..."


def format_order_money(model: Any, name: str) -> str:
    cents = getattr(model, name, None)
    if cents is None:
        return "—"
    return format_cents_for_ui(int(cents))


def validate_json_text(value: Any, field_label: str) -> str:
    """Ensure a form field is valid JSON object (stored as text)."""
    if value is None or value == "":
        return "{}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    if not text:
        return "{}"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, (dict, list)):
        raise ValueError(f"{field_label} must be a JSON object or array.")
    return text


async def aggregate_completed_order_stats(session: AsyncSession) -> dict[str, int]:
    """Sales stats from order snapshots (COMPLETED only)."""
    row = (
        await session.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_cents), 0),
                func.coalesce(func.sum(Order.profit_cents), 0),
            ).where(Order.status == OrderStatus.COMPLETED)
        )
    ).one()
    count, revenue, profit = row
    return {
        "completed_orders": int(count or 0),
        "revenue_cents": int(revenue or 0),
        "profit_cents": int(profit or 0),
    }


async def run_manual_refund(order_id: int, operator_id: int) -> tuple[str, bool]:
    """Refund one order; returns (message, credited)."""
    from bot.database import Database
    from bot.database.methods.orders import (
        OrderError,
        OrderTransitionError,
        manual_refund_order,
    )

    async with Database().session() as session:
        try:
            order, credited = await manual_refund_order(session, order_id, operator_id)
            await session.commit()
        except OrderError:
            return "Order not found.", False
        except OrderTransitionError as exc:
            return f"Refund not allowed: {exc}", False

    if credited:
        return f"Order #{order.id} refunded ({order.total_cents} kopecks credited).", True
    return f"Order #{order.id} was already refunded.", False
