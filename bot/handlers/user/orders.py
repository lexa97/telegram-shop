"""Order history for users (ТЗ-11)."""

from functools import partial

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.database import Database
from bot.database.methods.lazy_queries import query_user_orders
from bot.database.models.main import BoughtGoods, Goods
from bot.database.models.orders import Order, OrderStatus
from bot.i18n import localize, esc
from bot.keyboards.inline import back, lazy_paginated_keyboard
from bot.misc import LazyPaginator
from bot.money import format_cents_for_ui

router = Router()


def _status_label(status: str) -> str:
    key = f"shop.order.status.{status}"
    text = localize(key)
    return text if text != key else status


@router.callback_query(F.data == "my_orders")
async def my_orders_handler(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    paginator = LazyPaginator(partial(query_user_orders, user_id), per_page=8)
    page = 0
    items = await paginator.get_page(page)
    if not items:
        await call.message.edit_text(
            localize("shop.orders.empty"),
            reply_markup=back("profile"),
        )
        return

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda row: localize(
            "shop.orders.list_line",
            order_id=row["id"],
            name=row["goods_name"],
            status=_status_label(row["status"]),
        ),
        item_callback=lambda row: f"order_od:{row['id']}",
        page=page,
        back_cb="profile",
        nav_cb_prefix="orders-page_",
    )
    await call.message.edit_text(localize("shop.orders.title"), reply_markup=markup)


@router.callback_query(F.data.startswith("orders-page_"))
async def my_orders_page_handler(call: CallbackQuery, state: FSMContext):
    try:
        page = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return
    user_id = call.from_user.id
    paginator = LazyPaginator(partial(query_user_orders, user_id), per_page=8)
    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda row: localize(
            "shop.orders.list_line",
            order_id=row["id"],
            name=row["goods_name"],
            status=_status_label(row["status"]),
        ),
        item_callback=lambda row: f"order_od:{row['id']}",
        page=page,
        back_cb="profile",
        nav_cb_prefix="orders-page_",
    )
    await call.message.edit_text(localize("shop.orders.title"), reply_markup=markup)


@router.callback_query(F.data.startswith("order_od:"))
async def order_detail_handler(call: CallbackQuery, state: FSMContext):
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return

    user_id = call.from_user.id
    async with Database().session() as s:
        row = (
            await s.execute(
                select(Order, Goods.name)
                .join(Goods, Goods.id == Order.goods_id)
                .where(Order.id == order_id, Order.user_id == user_id)
            )
        ).first()
        if not row:
            await call.answer(localize("shop.orders.not_found"), show_alert=True)
            return
        order, goods_name = row
        bought = None
        if order.status == OrderStatus.COMPLETED:
            bought = (
                await s.execute(
                    select(BoughtGoods).where(BoughtGoods.order_id == order.id).limit(1)
                )
            ).scalar_one_or_none()

    lines = [
        localize("shop.orders.detail_title", order_id=order.id),
        localize("shop.orders.detail_goods", name=esc(goods_name)),
        localize("shop.orders.detail_status", status=_status_label(order.status)),
        localize(
            "shop.orders.detail_total",
            amount=format_cents_for_ui(order.total_cents),
        ),
    ]
    buttons = []
    if bought is not None:
        lines.append(localize("shop.orders.detail_delivered"))
        buttons.append(
            (localize("btn.view_delivery"), f"bought-item:{bought.id}:my_orders")
        )
    elif order.status in (OrderStatus.PROCESSING, OrderStatus.CREATED):
        lines.append(localize("shop.orders.detail_pending"))
    elif order.status == OrderStatus.FAILED:
        lines.append(localize("shop.orders.detail_failed"))
    elif order.status == OrderStatus.REFUNDED:
        lines.append(localize("shop.orders.detail_refunded"))
    elif order.status == OrderStatus.EXPIRED:
        lines.append(localize("shop.orders.detail_expired"))

    buttons.append((localize("btn.back"), "my_orders"))
    from bot.keyboards.inline import simple_buttons

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=simple_buttons(buttons, per_row=1),
    )
