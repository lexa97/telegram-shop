"""Shared steps for integration flow tests (mock Telegram, real test DB)."""

from aiogram.enums.chat_type import ChatType

from bot.handlers.user.cart import add_to_cart_handler
from bot.handlers.user.shop_and_goods import (
    items_list_callback_handler,
    item_info_callback_handler,
    shop_callback_handler,
)


async def user_starts_shop(make_callback_query, fsm_context, user_id: int) -> None:
    """Open shop categories (first step after /start)."""
    call = make_callback_query(data="shop", user_id=user_id)
    await shop_callback_handler(call, fsm_context)


async def add_catalog_item_to_cart(
    make_callback_query,
    fsm_context,
    user_id: int,
    item_index: int,
    *,
    open_shop: bool = False,
) -> None:
    """Pick item by index on page 0 of the first category and add to cart."""
    if open_shop:
        await user_starts_shop(make_callback_query, fsm_context, user_id)

    call = make_callback_query(data="cat:0:0", user_id=user_id)
    await items_list_callback_handler(call, fsm_context)

    call = make_callback_query(data=f"itm:{item_index}:0", user_id=user_id)
    await item_info_callback_handler(call, fsm_context)

    call = make_callback_query(data="add_to_cart", user_id=user_id)
    await add_to_cart_handler(call, fsm_context)


def private_start_message(make_message, user_id: int, text: str = "/start"):
    msg = make_message(text=text, user_id=user_id)
    msg.chat.type = ChatType.PRIVATE
    return msg
