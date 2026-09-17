"""Shared purchase UX (ТЗ-11): confirm, errors, receipts."""

from __future__ import annotations

from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database.methods import buy_item_transaction
from bot.database.methods.audit import log_audit_bg
from bot.database.methods.read import get_item_info_cached
from bot.database.methods.pricing import effective_price
from bot.handlers.other import is_safe_item_name, caller_name
from bot.i18n import localize, esc
from bot.keyboards.inline import simple_buttons, back
from bot.misc import EnvKeys, ItemPurchaseRequest, validate_telegram_id
from bot.misc.metrics import get_metrics
from bot.money import format_cents_for_ui
from bot.database.models.orders import OrderStatus
from bot.logger_mesh import logger

PURCHASE_ERROR_KEYS = {
    "user_not_found": "shop.purchase.fail.user_not_found",
    "item_not_found": "shop.item.not_found",
    "insufficient_funds": "shop.insufficient_funds",
    "out_of_stock": "shop.out_of_stock",
    "promo_invalid": "promo.not_found",
    "promo_expired": "promo.expired",
    "promo_max_uses": "promo.max_uses_reached",
    "promo_already_used": "promo.already_used",
    "promo_min_order": "promo.min_order",
    "promo_wrong_item": "promo.wrong_item",
    "promo_wrong_category": "promo.wrong_category",
    "gift_not_allowed": "shop.gift.not_allowed",
    "gift_recipient_not_registered": "shop.gift.recipient_not_registered",
    "no_provider_link": "shop.purchase.fail.no_provider",
}


def purchase_error_keyboard(error_code: str):
    if error_code == "insufficient_funds":
        return simple_buttons(
            [
                (localize("btn.replenish"), "replenish_balance"),
                (localize("btn.back"), "back_to_item"),
            ],
            per_row=1,
        )
    return back("back_to_item")


async def _validate_purchase_context(
    call: CallbackQuery, state: FSMContext
) -> tuple[str | None, int | None]:
    data = await state.get_data()
    raw_item_name = data.get("csrf_item")
    if not raw_item_name:
        await call.answer(localize("middleware.security.invalid_csrf"), show_alert=True)
        return None, None
    if not is_safe_item_name(raw_item_name):
        await call.answer(localize("errors.invalid_item_name"), show_alert=True)
        return None, None
    try:
        user_id = validate_telegram_id(call.from_user.id)
    except ValueError:
        await call.answer(localize("errors.invalid_user"), show_alert=True)
        return None, None
    return raw_item_name, user_id


async def build_purchase_confirm(
    state: FSMContext,
    item_name: str,
    *,
    gift_recipient_id: int | None = None,
) -> tuple[str, object] | None:
    item_info_data = await get_item_info_cached(item_name)
    if not item_info_data:
        return None

    price, _on_sale, _original_price = effective_price(item_info_data)
    price_text = format_cents_for_ui(price)

    if gift_recipient_id is not None:
        text = localize(
            "shop.purchase.confirm_gift",
            item_name=esc(item_name),
            price=price_text,
            currency=EnvKeys.PAY_CURRENCY,
            recipient_id=gift_recipient_id,
        )
        await state.update_data(pending_gift_recipient=gift_recipient_id)
    else:
        await state.update_data(pending_gift_recipient=None)
        text = localize(
            "shop.purchase.confirm_self",
            item_name=esc(item_name),
            price=price_text,
            currency=EnvKeys.PAY_CURRENCY,
        )

    markup = simple_buttons(
        [
            (localize("btn.confirm_purchase"), "buy_confirm"),
            (localize("btn.cancel"), "back_to_item"),
        ],
        per_row=1,
    )
    return text, markup


async def show_purchase_confirm(
    call: CallbackQuery,
    state: FSMContext,
    *,
    gift_recipient_id: int | None = None,
) -> None:
    item_name, user_id = await _validate_purchase_context(call, state)
    if not item_name or user_id is None:
        return

    built = await build_purchase_confirm(state, item_name, gift_recipient_id=gift_recipient_id)
    if not built:
        await call.answer(localize("shop.item.not_found"), show_alert=True)
        return
    text, markup = built
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)


async def execute_confirmed_purchase(call: CallbackQuery, state: FSMContext) -> None:
    item_name, user_id = await _validate_purchase_context(call, state)
    if not item_name or user_id is None:
        return

    data = await state.get_data()
    promo_code = data.get("applied_promo")
    gift_recipient = data.get("pending_gift_recipient")
    if gift_recipient is not None:
        try:
            gift_recipient = int(gift_recipient)
        except (TypeError, ValueError):
            gift_recipient = None

    await call.answer(localize("shop.purchase.processing"))

    metrics = get_metrics()
    success, message, purchase_data = await buy_item_transaction(
        user_id,
        item_name,
        promo_code=promo_code,
        gift_recipient_telegram_id=gift_recipient,
    )

    if not success:
        error_key = PURCHASE_ERROR_KEYS.get(message, "shop.purchase.fail.general")
        error_text = localize(error_key, message=message)
        await call.message.edit_text(
            error_text,
            reply_markup=purchase_error_keyboard(message),
        )
        if message not in PURCHASE_ERROR_KEYS:
            await log_audit_bg(
                "purchase_error",
                level="ERROR",
                user_id=user_id,
                resource_type="Item",
                resource_id=item_name,
                details=message,
            )
        return

    await state.update_data(applied_promo=None, pending_gift_recipient=None)

    if metrics:
        metrics.track_event(
            "purchase",
            call.from_user.id,
            {"item": item_name, "price": purchase_data["price"]},
        )
        metrics.track_conversion("purchase_funnel", "purchase", call.from_user.id)

    order_status = purchase_data.get("order_status")
    is_gift = gift_recipient is not None
    is_processing = order_status == OrderStatus.PROCESSING or not purchase_data.get("value")

    if is_processing and not is_gift:
        await call.message.edit_text(
            localize(
                "shop.purchase.processing_order",
                item_name=esc(item_name),
                order_id=purchase_data.get("order_id"),
            ),
            parse_mode="HTML",
            reply_markup=simple_buttons(
                [
                    (localize("btn.my_orders"), "my_orders"),
                    (localize("btn.back"), "back_to_item"),
                ],
                per_row=1,
            ),
        )
    elif is_gift:
        await call.message.edit_text(
            localize(
                "shop.purchase.gift_sent",
                item_name=esc(item_name),
                recipient_id=gift_recipient,
                order_id=purchase_data.get("order_id"),
            ),
            parse_mode="HTML",
            reply_markup=simple_buttons([(localize("btn.back"), "back_to_item")]),
        )
    else:
        safe_value = esc(purchase_data["value"])
        username = esc(call.from_user.username or call.from_user.first_name)
        buttons = [
            (f"📦 {purchase_data['item_name']}", f"bought-item:{purchase_data['bought_id']}:back_to_item"),
            (localize("btn.back"), "back_to_item"),
        ]
        await call.message.edit_text(
            localize(
                "shop.purchase.receipt",
                item_name=esc(purchase_data["item_name"]),
                price=purchase_data["price"],
                unique_id=purchase_data["unique_id"],
                datetime=purchase_data["bought_datetime"],
                username=username,
                user_id=call.from_user.id,
                value=safe_value,
                currency=EnvKeys.PAY_CURRENCY,
            ),
            parse_mode="HTML",
            reply_markup=simple_buttons(buttons),
        )

    await log_audit_bg(
        "purchase",
        user_id=user_id,
        resource_type="Item",
        resource_id=item_name[:100],
        details=(
            f"name={caller_name(call)[:50]}, "
            f"price={purchase_data['price']} {EnvKeys.PAY_CURRENCY}, "
            f"gift_to={gift_recipient}, order_id={purchase_data.get('order_id')}"
        ),
    )
