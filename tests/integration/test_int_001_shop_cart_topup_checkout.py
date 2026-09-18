"""Scenario INT-001: shop → cart → top-up → checkout (mock Telegram)."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update

from bot.database.main import Database
from bot.database.methods.read import check_user, get_cart_count, select_user_items
from bot.database.models.payment_config import PaymentInstrument
from bot.handlers.user.balance_and_payment import (
    checking_payment,
    process_replenish_balance,
    replenish_balance_amount,
    replenish_balance_callback_handler,
)
from bot.handlers.user.cart import (
    cart_checkout_confirm_handler,
    cart_checkout_handler,
    view_cart_handler,
)
from bot.handlers.user.main import profile_callback_handler, start
from bot.money import rub_to_cents
from bot.states import BalanceStates
from tests.integration.helpers import add_catalog_item_to_cart, private_start_message


USER_ID = 901_001
CART_TOTAL_RUB = 150  # 60 + 40 + 50
TOPUP_RUB = 200


async def _enable_cryptopay_instrument() -> None:
    async with Database().session() as s:
        await s.execute(
            update(PaymentInstrument)
            .where(PaymentInstrument.code == "cryptopay")
            .values(enabled=True)
        )


@pytest.mark.asyncio
class TestInt001ShopCartTopupCheckout:
    """Scenario: INT-001 — старт, разные типы товаров в корзину, пополнение, оплата корзины."""

    async def test_full_purchase_flow(
        self,
        make_message,
        make_callback_query,
        fsm_context,
        category_factory,
        item_factory,
    ):
        await category_factory("IntShop")
        await item_factory(
            name="AlphaKey",
            price=60,
            category="IntShop",
            values=[("KEY-ALPHA", False)],
        )
        await item_factory(
            name="BetaKey",
            price=40,
            category="IntShop",
            values=[("KEY-BETA", False)],
        )
        await item_factory(
            name="GammaLicense",
            price=50,
            category="IntShop",
            values=[("LICENSE-INF", True)],
        )

        msg = private_start_message(make_message, USER_ID)
        with patch("bot.handlers.user.main.EnvKeys") as env:
            env.OWNER_ID = 999_999
            env.CHANNEL_URL = ""
            env.HELPER_ID = ""
            env.RULES = ""
            await start(msg, fsm_context)

        user = await check_user(USER_ID)
        assert user is not None
        assert user["balance"] == 0

        await add_catalog_item_to_cart(
            make_callback_query, fsm_context, USER_ID, 0, open_shop=True,
        )
        await add_catalog_item_to_cart(make_callback_query, fsm_context, USER_ID, 1)
        await add_catalog_item_to_cart(make_callback_query, fsm_context, USER_ID, 2)

        assert await get_cart_count(USER_ID) == 3

        call = make_callback_query(data="cart", user_id=USER_ID)
        await view_cart_handler(call, fsm_context)
        cart_text = call.message.edit_text.call_args[0][0]
        assert str(CART_TOTAL_RUB) in cart_text

        call = make_callback_query(data="profile", user_id=USER_ID)
        await profile_callback_handler(call, fsm_context)

        with patch(
            "bot.handlers.user.balance_and_payment.payment_methods_available",
            new_callable=AsyncMock,
            return_value=True,
        ):
            call = make_callback_query(data="replenish_balance", user_id=USER_ID)
            await replenish_balance_callback_handler(call, fsm_context)
        assert await fsm_context.get_state() == BalanceStates.waiting_amount

        amount_msg = make_message(text=str(TOPUP_RUB), user_id=USER_ID)
        with patch("bot.handlers.user.balance_and_payment.EnvKeys") as env:
            env.MIN_AMOUNT = 10
            env.MAX_AMOUNT = 100_000
            env.PAY_CURRENCY = "RUB"
            await replenish_balance_amount(amount_msg, fsm_context)
        assert await fsm_context.get_state() == BalanceStates.waiting_payment

        await _enable_cryptopay_instrument()

        mock_crypto = AsyncMock()
        mock_crypto.create_invoice = AsyncMock(
            return_value={
                "invoice_id": 901001,
                "mini_app_invoice_url": "https://example.test/invoice",
            }
        )
        mock_crypto.get_invoice = AsyncMock(
            return_value={"status": "paid", "amount": f"{TOPUP_RUB}.00"},
        )

        pay_call = make_callback_query(data="pay_inst_cryptopay", user_id=USER_ID)
        with patch(
            "bot.handlers.user.balance_and_payment.CryptoPayAPI",
            return_value=mock_crypto,
        ), patch("bot.handlers.user.balance_and_payment.EnvKeys") as env:
            env.CRYPTO_PAY_TOKEN = "test_token"
            env.PAY_CURRENCY = "RUB"
            env.PAYMENT_TIME = 1800
            env.REFERRAL_PERCENT = 0
            await process_replenish_balance(pay_call, fsm_context)

        check_call = make_callback_query(data="check", user_id=USER_ID)
        with patch(
            "bot.handlers.user.balance_and_payment.CryptoPayAPI",
            return_value=mock_crypto,
        ), patch("bot.handlers.user.balance_and_payment.EnvKeys") as env:
            env.REFERRAL_PERCENT = 0
            env.PAY_CURRENCY = "RUB"
            await checking_payment(check_call, fsm_context)

        user = await check_user(USER_ID)
        assert user["balance"] == rub_to_cents(TOPUP_RUB)

        call = make_callback_query(data="cart_checkout", user_id=USER_ID)
        await cart_checkout_handler(call, fsm_context)

        call = make_callback_query(data="cart_checkout_confirm", user_id=USER_ID)
        await cart_checkout_confirm_handler(call, fsm_context)

        receipt_text = call.message.edit_text.call_args[0][0]
        assert "150" in receipt_text
        assert "3" in receipt_text

        user = await check_user(USER_ID)
        assert user["balance"] == rub_to_cents(TOPUP_RUB - CART_TOTAL_RUB)
        assert await get_cart_count(USER_ID) == 0
        assert await select_user_items(USER_ID) == 3
