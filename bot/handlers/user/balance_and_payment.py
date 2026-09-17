import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, SuccessfulPayment
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.database.methods import get_user_referral, process_payment_with_referral, create_pending_payment
from bot.handlers.user.purchase_ui import show_purchase_confirm, execute_confirmed_purchase
from bot.keyboards import back, payment_menu, close, get_payment_choice, payment_choice_from_instruments
from bot.logger_mesh import logger
from bot.database.methods.audit import log_audit
from bot.database.methods.cache_utils import safe_create_task
from bot.misc import EnvKeys, ItemPurchaseRequest, validate_telegram_id, validate_money_amount, PaymentRequest
from bot.handlers.other import payment_methods_available, is_safe_item_name, caller_name
from bot.payments.credit import process_payment_topup
from bot.payments.service import (
    create_topup_via_instrument,
    get_instrument_by_code,
    list_enabled_instruments,
)
from bot.payments.gateways.platega import fetch_status as platega_fetch_status, gateway_config_from_json
from bot.payments.gateway_settings import (
    cryptopay_api_token,
    gateway_is_configured,
    stars_per_value,
    telegram_provider_token,
)
from bot.misc.metrics import get_metrics
from bot.misc.services import CryptoPayAPI, CryptoPayAPIError, send_stars_invoice, send_fiat_invoice
from bot.misc.services.payment import _minor_units_for, payload_amount
from bot.money import rub_to_cents, format_cents_for_ui, cents_to_float_rub
from bot.filters import ValidAmountFilter
from bot.i18n import localize, esc
from bot.states import BalanceStates

router = Router()


async def _notify_referrer_bonus(bot, user_id: int, amount_cents: int, payer_name: str, payer_id: int):
    """Send referral bonus notification to the referrer if applicable."""
    referral_id = await get_user_referral(user_id)
    if not referral_id or not EnvKeys.REFERRAL_PERCENT:
        return
    try:
        clamped_percent = min(max(EnvKeys.REFERRAL_PERCENT, 0), 99)
        bonus_cents = (amount_cents * clamped_percent) // 100
        if bonus_cents > 0:
            await bot.send_message(
                referral_id,
                localize('payments.referral.bonus',
                         amount=format_cents_for_ui(bonus_cents), name=esc(payer_name),
                         id=payer_id, currency=EnvKeys.PAY_CURRENCY),
                reply_markup=close()
            )
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.error(f"Failed to send referral notification to user {referral_id}: {e}")


@router.callback_query(F.data == "replenish_balance")
async def replenish_balance_callback_handler(call: CallbackQuery, state: FSMContext):
    """Ask user for the amount if at least one payment method is enabled."""
    if not await payment_methods_available():
        await call.answer(localize("payments.not_configured"), show_alert=True)
        return

    await call.message.edit_text(
        localize("payments.replenish_prompt", currency=EnvKeys.PAY_CURRENCY),
        reply_markup=back('profile')
    )
    await state.set_state(BalanceStates.waiting_amount)


@router.message(BalanceStates.waiting_amount, ValidAmountFilter())
async def replenish_balance_amount(message: Message, state: FSMContext):
    """Store amount and show payment methods."""
    try:
        # Validate amount using Pydantic
        amount = validate_money_amount(
            message.text,
            min_amount=Decimal(EnvKeys.MIN_AMOUNT),
            max_amount=Decimal(EnvKeys.MAX_AMOUNT)
        )

        await state.update_data(amount_cents=amount)

        instruments = await list_enabled_instruments()
        keyboard = (
            payment_choice_from_instruments(instruments)
            if instruments
            else get_payment_choice()
        )
        await message.answer(
            localize("payments.method_choose"),
            reply_markup=keyboard,
        )
        await state.set_state(BalanceStates.waiting_payment)

    except ValueError:
        await message.answer(
            localize("payments.replenish_invalid",
                     min_amount=EnvKeys.MIN_AMOUNT,
                     max_amount=EnvKeys.MAX_AMOUNT,
                     currency=EnvKeys.PAY_CURRENCY),
            reply_markup=back('replenish_balance')
        )


@router.message(BalanceStates.waiting_amount)
async def invalid_amount(message: Message, state: FSMContext):
    """
    Tell user the amount is invalid.
    """
    await message.answer(
        localize("payments.replenish_invalid",
                 min_amount=EnvKeys.MIN_AMOUNT,
                 max_amount=EnvKeys.MAX_AMOUNT,
                 currency=EnvKeys.PAY_CURRENCY),
        reply_markup=back('replenish_balance')
    )


_LEGACY_PAY_MAP = {
    "pay_cryptopay": "cryptopay",
    "pay_stars": "stars",
    "pay_fiat": "telegram_fiat",
}


def _instrument_code_from_callback(data: str) -> str | None:
    if data.startswith("pay_inst_"):
        return data.removeprefix("pay_inst_")
    return _LEGACY_PAY_MAP.get(data)


@router.callback_query(
    BalanceStates.waiting_payment,
    F.data.startswith("pay_inst_") | F.data.in_(["pay_cryptopay", "pay_stars", "pay_fiat"]),
)
async def process_replenish_balance(call: CallbackQuery, state: FSMContext):
    """Create an invoice for the chosen payment method."""
    data = await state.get_data()
    amount_cents = data.get('amount_cents')
    if amount_cents is None and data.get('amount') is not None:
        amount_cents = rub_to_cents(data.get('amount'))

    if amount_cents is None:
        await call.answer(localize("payments.session_expired"), show_alert=True)
        await call.message.edit_text(localize("menu.title"), reply_markup=back('back_to_menu'))
        await state.clear()
        return

    inst_code = _instrument_code_from_callback(call.data)
    instrument = await get_instrument_by_code(inst_code) if inst_code else None
    if not instrument or not instrument.enabled:
        await call.answer(localize("payments.not_configured"), show_alert=True)
        return

    gateway = instrument.gateway
    gateway_code = gateway.code
    if not gateway_is_configured(gateway):
        await call.answer(localize("payments.not_configured"), show_alert=True)
        return

    try:
        amount_dec = Decimal(amount_cents) / Decimal(100)
        payment_request = PaymentRequest(
            amount=amount_dec,
            currency=EnvKeys.PAY_CURRENCY,
            provider=gateway_code,
        )
        ttl_seconds = int(EnvKeys.PAYMENT_TIME)

        if gateway_code == "platega":
            try:
                created = await create_topup_via_instrument(
                    instrument=instrument,
                    user_id=call.from_user.id,
                    amount_cents=amount_cents,
                    username=call.from_user.username,
                )
            except Exception as e:
                await log_audit(
                    "platega_invoice_fail",
                    level="ERROR",
                    user_id=call.from_user.id,
                    resource_type="Payment",
                    details=str(e),
                )
                await call.answer(localize("payments.fiat.create_fail", error=str(e)), show_alert=True)
                return

            await state.update_data(
                invoice_id=created.external_id,
                payment_type="platega",
            )
            await call.message.edit_text(
                localize(
                    "payments.invoice.summary",
                    amount=int(amount_dec),
                    minutes=int(ttl_seconds / 60),
                    button=localize("btn.check_payment"),
                    currency=payment_request.currency,
                ),
                reply_markup=payment_menu(created.payment_url),
            )
            return

        if gateway_code == "cryptopay":
            try:
                crypto = CryptoPayAPI(cryptopay_api_token(gateway))
                invoice = await crypto.create_invoice(
                    amount=float(amount_dec),
                    expires_in=ttl_seconds,
                    currency=payment_request.currency,
                    accepted_assets="TON,USDT,BTC,ETH",
                    payload=str(call.from_user.id),
                )
            except CryptoPayAPIError as e:
                await log_audit("cryptopay_error", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=f"[{e.code}] {e.name}")
                await call.answer(localize("payments.crypto.api_error", error=e.name), show_alert=True)
                return
            except Exception as e:
                await log_audit("cryptopay_invoice_fail", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=str(e))
                await call.answer(localize("payments.crypto.create_fail", error=str(e)), show_alert=True)
                return

            pay_url = invoice.get("mini_app_invoice_url")
            invoice_id = invoice.get("invoice_id")

            await create_pending_payment(
                provider="cryptopay",
                external_id=str(invoice_id),
                user_id=call.from_user.id,
                amount=amount_cents,
                currency=payment_request.currency,
            )

            await state.update_data(invoice_id=invoice_id, payment_type="cryptopay")

            await call.message.edit_text(
                localize("payments.invoice.summary",
                         amount=int(amount_dec),
                         minutes=int(ttl_seconds / 60),
                         button=localize("btn.check_payment"),
                         currency=payment_request.currency),
                reply_markup=payment_menu(pay_url)
            )

        elif gateway_code == "stars":
            rate = stars_per_value(gateway)
            if rate > 0:
                try:
                    await send_stars_invoice(
                        bot=call.message.bot,
                        chat_id=call.from_user.id,
                        amount=int(amount_dec),
                        stars_per_value=rate,
                    )
                except Exception as e:
                    await log_audit("stars_invoice_fail", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=str(e))
                    await call.answer(localize("payments.stars.create_fail", error=str(e)), show_alert=True)
                    return
                await state.clear()
            else:
                await call.answer(localize("payments.not_configured"), show_alert=True)
                return

        elif gateway_code == "telegram_fiat":
            provider_token = telegram_provider_token(gateway)
            if not provider_token:
                await call.answer(localize("payments.not_configured"), show_alert=True)
                return

            try:
                await send_fiat_invoice(
                    bot=call.message.bot,
                    chat_id=call.from_user.id,
                    amount=int(amount_dec),
                    provider_token=provider_token,
                )
            except Exception as e:
                await log_audit("fiat_invoice_fail", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=str(e))
                await call.answer(localize("payments.fiat.create_fail", error=str(e)), show_alert=True)
                return
            await state.clear()

    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        await state.clear()
        await call.answer(localize("errors.something_wrong"), show_alert=True)


@router.callback_query(F.data == "check")
async def checking_payment(call: CallbackQuery, state: FSMContext):
    """
    Check CryptoPay invoice status and credit balance if paid.
    """
    user_id = call.from_user.id
    data = await state.get_data()
    payment_type = data.get("payment_type")

    if not payment_type:
        await call.answer(localize("payments.no_active_invoice"), show_alert=True)
        return

    if payment_type == "cryptopay":
        invoice_id = data.get("invoice_id")
        if not invoice_id:
            await call.answer(localize("payments.invoice_not_found"), show_alert=True)
            await state.clear()
            return

        try:
            inst = await get_instrument_by_code("cryptopay")
            gw = inst.gateway if inst else None
            token = cryptopay_api_token(gw) if gw else None
            if not token:
                await call.answer(localize("payments.not_configured"), show_alert=True)
                return
            crypto = CryptoPayAPI(token)
            info = await crypto.get_invoice(invoice_id)
        except CryptoPayAPIError as e:
            await log_audit("cryptopay_check_error", level="ERROR", user_id=user_id, resource_type="Payment", details=f"[{e.code}] {e.name}")
            await call.answer(localize("payments.crypto.api_error", error=e.name), show_alert=True)
            return
        except Exception as e:
            await log_audit("cryptopay_get_fail", level="ERROR", user_id=user_id, resource_type="Payment", details=str(e))
            await call.answer(localize("payments.crypto.check_fail", error=str(e)), show_alert=True)
            return

        status = info.get("status")
        if status == "paid":
            balance_amount_cents = rub_to_cents(
                Decimal(str(info.get("amount", "0"))).quantize(Decimal("0.01"))
            )

            if balance_amount_cents <= 0:
                await call.answer(localize("payments.unable_determine_amount"), show_alert=True)
                return

            # Use transactional payment processing
            success, error_msg = await process_payment_topup(
                user_id=user_id,
                amount=balance_amount_cents,
                provider="cryptopay",
                external_id=str(invoice_id),
            )

            if not success:
                if error_msg == "already_processed":
                    await call.answer(localize("payments.already_processed"), show_alert=True)
                else:
                    await call.answer(localize("errors.general_error", e=error_msg), show_alert=True)
                return

            metrics = get_metrics()
            if metrics:
                metrics.track_event("payment", user_id, {"amount": balance_amount_cents, "provider": "cryptopay"})

            # Send a notification to the referrer
            await _notify_referrer_bonus(
                call.bot, user_id, balance_amount_cents, call.from_user.first_name, call.from_user.id,
            )

            await call.message.edit_text(
                localize("payments.topped_simple",
                         amount=format_cents_for_ui(balance_amount_cents),
                         currency=EnvKeys.PAY_CURRENCY),
                reply_markup=back('profile')
            )
            await state.clear()

            safe_create_task(log_audit(
                "balance_replenish",
                user_id=user_id,
                resource_type="Payment",
                details=f"name={caller_name(call)}, amount={format_cents_for_ui(balance_amount_cents)} {EnvKeys.PAY_CURRENCY}, provider=cryptopay",
            ))

        elif status == "active":
            await call.answer(localize("payments.not_paid_yet"))
        else:
            await call.answer(localize("payments.expired"), show_alert=True)

    elif payment_type == "platega":
        invoice_id = data.get("invoice_id")
        if not invoice_id:
            await call.answer(localize("payments.invoice_not_found"), show_alert=True)
            await state.clear()
            return
        instrument = await get_instrument_by_code("card_mir")
        if not instrument:
            await call.answer(localize("payments.not_configured"), show_alert=True)
            return
        cfg = gateway_config_from_json(instrument.gateway.config_json)
        try:
            info = await platega_fetch_status(cfg, str(invoice_id))
        except Exception as e:
            await log_audit(
                "platega_check_error",
                level="ERROR",
                user_id=user_id,
                resource_type="Payment",
                details=str(e),
            )
            await call.answer(localize("payments.crypto.check_fail", error=str(e)), show_alert=True)
            return
        if info.paid:
            from bot.database.main import Database
            from bot.database.models import Payments
            from sqlalchemy import select

            pending_amount = data.get("amount_cents")
            async with Database().session() as s:
                row = (
                    await s.execute(
                        select(Payments).where(
                            Payments.provider == "platega",
                            Payments.external_id == str(invoice_id),
                        )
                    )
                ).scalars().first()
                if row:
                    pending_amount = row.amount
            if not pending_amount:
                await call.answer(localize("payments.unable_determine_amount"), show_alert=True)
                return

            success, error_msg = await process_payment_topup(
                user_id=user_id,
                amount=int(pending_amount),
                provider="platega",
                external_id=str(invoice_id),
            )
            if not success and error_msg != "already_processed":
                await call.answer(localize("errors.general_error", e=error_msg), show_alert=True)
                return
            await call.message.edit_text(
                localize(
                    "payments.topped_simple",
                    amount=format_cents_for_ui(int(pending_amount)),
                    currency=EnvKeys.PAY_CURRENCY,
                ),
                reply_markup=back("profile"),
            )
            await state.clear()
        else:
            await call.answer(localize("payments.not_paid_yet"))


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    """Validate the payment before Telegram processes it."""
    try:
        payload = json.loads(query.invoice_payload or "{}")
    except Exception:
        await query.answer(ok=False, error_message="Invalid payload")
        return

    amount = payload_amount(payload)
    if amount <= 0:
        await query.answer(ok=False, error_message="Invalid amount")
        return

    if amount < int(EnvKeys.MIN_AMOUNT):
        await query.answer(ok=False, error_message="Amount below minimum")
        return

    if amount > int(EnvKeys.MAX_AMOUNT):
        await query.answer(ok=False, error_message="Amount exceeds maximum")
        return

    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """
    Handle successful payment:
    - XTR (Stars): total_amount is ⭐. take CURRENCY from payload (amount) or convert ⭐ → CURRENCY.
    - Fiat: total_amount is minor units; divide by 100 (or 1 for JPY/KRW).
    """
    sp: SuccessfulPayment = message.successful_payment
    user_id = message.from_user.id

    payload = {}
    try:
        if sp.invoice_payload:
            payload = json.loads(sp.invoice_payload)
    except Exception:
        payload = {}

    amount = payload_amount(payload)

    if amount <= 0:
        if sp.currency == "XTR":
            # Stars, no usable payload: reverse the conversion as a last resort.
            amount = int(
                (Decimal(int(sp.total_amount)) / Decimal(str(EnvKeys.STARS_PER_VALUE)))
                .to_integral_value(rounding=ROUND_HALF_UP)
            )
        else:
            # Fiat: total_amount is exact in minor units, so this is lossless.
            currency = sp.currency.upper()
            multiplier = _minor_units_for(currency)
            amount = int(Decimal(sp.total_amount) / Decimal(multiplier))

    if amount <= 0:
        await message.answer(localize("payments.unable_determine_amount"), reply_markup=close())
        return

    # Idempotence
    provider = "telegram" if sp.currency != "XTR" else "stars"
    external_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id
    if not external_id:
        digest = hashlib.sha256(
            f"{provider}|{user_id}|{sp.currency}|{sp.total_amount}|{sp.invoice_payload or ''}".encode()
        ).hexdigest()
        external_id = f"{provider}:fallback:{digest[:32]}"
        logger.warning(
            "successful_payment without a charge id for user %s (%s %s); "
            "falling back to a derived idempotency key %s",
            user_id, sp.total_amount, sp.currency, external_id,
        )

    amount_cents = rub_to_cents(amount)

    success, error_msg = await process_payment_with_referral(
        user_id=user_id,
        amount=amount_cents,
        provider=provider,
        external_id=external_id,
        referral_percent=EnvKeys.REFERRAL_PERCENT
    )

    if not success:
        if error_msg == "already_processed":
            await message.answer(localize("payments.already_processed"), reply_markup=close())
        else:
            await message.answer(localize("payments.processing_error"), reply_markup=close())
        return

    # Sending notification to referrer
    await _notify_referrer_bonus(
        message.bot, user_id, amount_cents, message.from_user.first_name, message.from_user.id,
    )

    metrics = get_metrics()
    if metrics:
        metrics.track_event("payment", user_id, {"amount": amount_cents, "provider": provider})

    suffix = localize("payments.success_suffix.stars") if sp.currency == "XTR" else localize(
        "payments.success_suffix.tg")
    await message.answer(
        localize(
            'payments.topped_with_suffix',
            amount=format_cents_for_ui(amount_cents),
            suffix=suffix,
            currency=EnvKeys.PAY_CURRENCY,
        ),
        reply_markup=back('profile')
    )

    safe_create_task(log_audit(
        "balance_replenish",
        user_id=user_id,
        resource_type="Payment",
        details=f"name={caller_name(message)}, amount={amount} {EnvKeys.PAY_CURRENCY}, provider={suffix}",
    ))


@router.callback_query(F.data == "buy_item")
async def buy_item_callback_handler(call: CallbackQuery, state: FSMContext):
    """Show purchase confirmation (ТЗ-11)."""
    await show_purchase_confirm(call, state)


@router.callback_query(F.data == "buy_confirm")
async def buy_confirm_handler(call: CallbackQuery, state: FSMContext):
    """Execute purchase after user confirmation."""
    try:
        await execute_confirmed_purchase(call, state)
    except Exception as e:
        logger.error(f"Critical error in purchase handler: {e}")
        await call.answer(localize("errors.something_wrong"), show_alert=True)
