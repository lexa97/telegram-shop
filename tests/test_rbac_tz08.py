"""ТЗ-08: встроенные роли и матрица прав."""

import pytest
from sqlalchemy import select

from bot.database import Database
from bot.database.methods.read import get_role_id_by_name
from bot.database.models import Permission
from bot.database.models.main import Role
from bot.keyboards.inline import admin_console_keyboard


@pytest.mark.asyncio
async def test_builtin_role_masks():
    async with Database().session() as s:
        by_name = {
            r.name: r.permissions
            for r in (await s.execute(select(Role))).scalars().all()
        }

    assert Permission.granted(by_name["USER"], Permission.USE)
    assert not Permission.granted(by_name["USER"], Permission.BALANCE_MANAGE)

    op = by_name["OPERATOR"]
    assert Permission.granted(op, Permission.USERS_MANAGE | Permission.ORDERS_MANAGE)
    assert not Permission.granted(op, Permission.ADMINS_MANAGE)
    assert not Permission.granted(op, Permission.PAYMENTS_CONFIG)
    assert not Permission.granted(op, Permission.BALANCE_MANAGE)

    mgr = by_name["MANAGER"]
    assert Permission.granted(mgr, Permission.CATALOG_MANAGE | Permission.PROMO_MANAGE)
    assert Permission.granted(mgr, Permission.PROVIDERS_MANAGE)
    assert not Permission.granted(mgr, Permission.BALANCE_MANAGE)
    assert not Permission.granted(mgr, Permission.OWN)

    admin = by_name["ADMIN"]
    assert Permission.granted(admin, Permission.BALANCE_MANAGE | Permission.PAYMENTS_CONFIG)
    assert not Permission.granted(admin, Permission.ADMINS_MANAGE)
    assert not Permission.granted(admin, Permission.OWN)

    superadmin = by_name["SUPERADMIN"]
    assert superadmin == Permission.all_bits()
    assert Permission.granted(superadmin, Permission.AUDIT_VIEW | Permission.ADMINS_MANAGE)


def test_operator_console_hides_roles_and_balance():
    op = (
        Permission.USE
        | Permission.USERS_MANAGE
        | Permission.ORDERS_MANAGE
        | Permission.TICKETS_MANAGE
        | Permission.STATS_VIEW
    )
    kb = admin_console_keyboard(role=op)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "user_management" in callbacks
    assert "shop_management" in callbacks
    assert "role_mgmt" not in callbacks
    assert "promo_mgmt" not in callbacks


def test_manager_console_catalog_without_users():
    mgr = (
        Permission.USE
        | Permission.CATALOG_MANAGE
        | Permission.PROMO_MANAGE
        | Permission.PROVIDERS_MANAGE
        | Permission.STATS_VIEW
    )
    kb = admin_console_keyboard(role=mgr)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "goods_management" in callbacks
    assert "promo_mgmt" in callbacks
    assert "user_management" not in callbacks
    assert "role_mgmt" not in callbacks


@pytest.mark.asyncio
async def test_order_refund_writes_audit():
    from decimal import Decimal

    from bot.database.methods.orders import (
        create_order_with_snapshot,
        manual_refund_order,
        transition_order,
    )
    from bot.database.models.main import AuditLog, Categories, Goods, User
    from bot.database.models.orders import OrderStatus
    from bot.money import rub_to_cents

    async with Database().session() as s:
        s.add(User(telegram_id=880001, balance=rub_to_cents(100)))
        s.add(Categories(name="rbac-cat"))
        await s.flush()
        cat = (await s.execute(select(Categories).where(Categories.name == "rbac-cat"))).scalar_one()
        goods = Goods(
            name="rbac-item",
            price=rub_to_cents(Decimal("10")),
            description="x",
            category_id=cat.id,
        )
        s.add(goods)
        await s.flush()
        order = await create_order_with_snapshot(
            s,
            user_id=880001,
            goods_id=goods.id,
            quantity=1,
            unit_price_rub=Decimal("10.00"),
        )
        await transition_order(s, order, OrderStatus.PROCESSING)
        await transition_order(s, order, OrderStatus.COMPLETED)
        await s.commit()
        oid = order.id

    async with Database().session() as s:
        await manual_refund_order(s, oid, operator_id=880002)
        await s.commit()

    async with Database().session() as s:
        rows = (
            await s.execute(
                select(AuditLog).where(
                    AuditLog.action == "order_refund",
                    AuditLog.resource_id == str(oid),
                    AuditLog.user_id == 880002,
                )
            )
        ).scalars().all()
        assert rows
