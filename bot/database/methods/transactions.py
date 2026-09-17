import asyncio
from datetime import datetime, timezone
from uuid import uuid4

_checkout_lock = asyncio.Lock()

from bot.money import cents_to_float_rub, rub_to_cents

from sqlalchemy import select, delete as sa_delete, update as sa_update
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError

from bot.database.models import User, ItemValues, Goods, Categories, BoughtGoods, Payments, Operations
from bot.database.models.main import PromoCodes, CartItems
from bot.database import Database
from bot.misc import EnvKeys
from bot.database.methods.read import (
    invalidate_user_cache, invalidate_stats_cache, invalidate_item_cache,
    invalidate_category_cache, promo_rule_error,
)
from bot.database.methods.cache_utils import safe_create_task
from bot.database.methods.pricing import effective_price, apply_promo_discount
from bot.database.methods.audit import log_audit
from bot.catalog.enums import FulfillmentType
from bot.catalog.stock import (
    StockAllocationError,
    consume_stock_units,
    count_finite_available_units,
)
from bot.misc.services.fulfillment import (
    FulfillmentError,
    begin_paid_order,
    fulfill_processing_order_by_id,
    purchase_api_line,
    purchase_result_from_order,
    purchase_stock_line,
)

# Canonical promo error code (from promo_rule_error) -> user-facing key per call site.
_BUY_PROMO_ERRORS = {
    "not_found": "promo_invalid",
    "inactive": "promo_invalid",
    "wrong_type": "promo_invalid",
    "expired": "promo_expired",
    "max_uses": "promo_max_uses",
    "already_used": "promo_already_used",
    "wrong_item": "promo_wrong_item",
    "wrong_category": "promo_wrong_category",
    "min_order": "promo_min_order",
}
_REDEEM_PROMO_ERRORS = {
    "not_found": "promo.not_found",
    "inactive": "promo.inactive",
    "wrong_type": "promo.not_balance_type",
    "expired": "promo.expired",
    "max_uses": "promo.max_uses_reached",
    "already_used": "promo.already_used",
}


class _Abort(Exception):
    """Abort the current transaction with a user-facing failure code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _split_amount(total_cents: int, n: int) -> list[int]:
    """Split line total kopecks across ``n`` unit rows; sum(result) == total_cents."""
    if n <= 0:
        return []
    base, extra = divmod(int(total_cents), n)
    return [base + (1 if i < extra else 0) for i in range(n)]


async def buy_item_transaction(
    telegram_id: int,
    item_name: str,
    promo_code: str = None,
    *,
    gift_recipient_telegram_id: int | None = None,
) -> tuple[bool, str, dict | None]:
    """
    Complete transactional purchase of goods with checks and locks.
    Returns: (success, message, purchase_data)
    """
    max_retries = 3
    for attempt in range(max_retries):
        api_order_id = None
        try:
            async with _checkout_lock:
                async with Database().session() as s:
                    user = (await s.execute(
                        select(User).where(User.telegram_id == telegram_id).with_for_update()
                    )).scalars().one_or_none()
                    if not user:
                        raise _Abort("user_not_found")

                    goods = (await s.execute(
                        select(Goods).where(Goods.name == item_name).with_for_update()
                    )).scalars().one_or_none()
                    if not goods:
                        raise _Abort("item_not_found")

                    price, _on_sale, _original_price = effective_price(goods)
                    final_price = price
                    discount_info = None

                    applied_promo = None
                    if promo_code:
                        promo = (await s.execute(
                            select(PromoCodes).where(PromoCodes.code == promo_code.upper()).with_for_update()
                        )).scalars().first()
                        err = await promo_rule_error(
                            s,
                            promo,
                            telegram_id,
                            goods=goods,
                            order_total_cents=price,
                        )
                        if err:
                            raise _Abort(_BUY_PROMO_ERRORS[err])
                        final_price = apply_promo_discount(
                            price, promo.discount_type, promo.discount_value, 1
                        )
                        applied_promo = promo
                        discount_info = {
                            "code": promo.code,
                            "original_price": cents_to_float_rub(price),
                            "discount": cents_to_float_rub(price - final_price),
                        }

                    discount_cents = price - final_price if promo_code else 0
                    cost_cents = 0
                    if goods.fulfillment_type == FulfillmentType.API:
                        from bot.providers.links import select_primary_link_for_session

                        link = await select_primary_link_for_session(s, goods.id)
                        if not link:
                            raise _Abort("no_provider_link")
                        cost_cents = int(link.cost_cents or 0)

                    try:
                        if goods.fulfillment_type == FulfillmentType.API:
                            order = await begin_paid_order(
                                s,
                                user=user,
                                goods=goods,
                                quantity=1,
                                unit_price_cents=price,
                                discount_cents=discount_cents,
                                gift_recipient_telegram_id=gift_recipient_telegram_id,
                                cost_cents=cost_cents,
                            )
                            await purchase_api_line(s, order, goods)
                            bought_rows = []
                            api_order_id = order.id
                        else:
                            delivered_values = await consume_stock_units(s, goods, 1)
                            order = await begin_paid_order(
                                s,
                                user=user,
                                goods=goods,
                                quantity=1,
                                unit_price_cents=price,
                                discount_cents=discount_cents,
                                gift_recipient_telegram_id=gift_recipient_telegram_id,
                                cost_cents=0,
                            )
                            bought_rows = await purchase_stock_line(
                                s, order, goods, 1, delivered_values=delivered_values
                            )
                    except FulfillmentError as exc:
                        raise _Abort(exc.code)
                    except StockAllocationError as exc:
                        raise _Abort(exc.code)

                    if applied_promo is not None:
                        from bot.database.methods.promo_usage import (
                            PromoUsageLimitError,
                            record_promo_usage,
                        )

                        try:
                            await record_promo_usage(
                                s, applied_promo, telegram_id, order_id=order.id
                            )
                        except PromoUsageLimitError as exc:
                            raise _Abort(_BUY_PROMO_ERRORS[exc.code])

                    result_data = purchase_result_from_order(
                        order, goods, bought_rows, user.balance, discount_info
                    )

        except _Abort as e:
            return False, e.code, None

        except IntegrityError as e:
            if "unique_id" in str(e).lower() and attempt < max_retries - 1:
                continue  # Retry with a new unique_id
            await log_audit(
                "purchase_failed",
                level="WARNING",
                user_id=telegram_id,
                resource_type="Item",
                resource_id=item_name,
                details=str(e),
            )
            return False, "transaction_error", None

        except Exception as e:
            await log_audit(
                "purchase_failed",
                level="WARNING",
                user_id=telegram_id,
                resource_type="Item",
                resource_id=item_name,
                details=str(e),
            )
            return False, "transaction_error", None

        # Invalidate caches only after the commit succeeded.
        safe_create_task(invalidate_user_cache(telegram_id))
        safe_create_task(invalidate_stats_cache())
        safe_create_task(invalidate_item_cache(item_name))
        if api_order_id is not None:
            safe_create_task(fulfill_processing_order_by_id(api_order_id))
        return True, "success", result_data

    return False, "transaction_error", None


async def process_payment_with_referral(
        user_id: int,
        amount: int,
        provider: str,
        external_id: str,
        referral_percent: int = 0
) -> tuple[bool, str]:
    """
    Processing a payment with a referral bonus in one transaction.
    Returns (success, message)
    """

    try:
        async with Database().session() as s:
            # 1. Check the idempotency of the payment
            existing_payment = (await s.execute(
                select(Payments).where(
                    Payments.provider == provider,
                    Payments.external_id == external_id
                ).with_for_update()
            )).scalars().first()

            if existing_payment:
                if existing_payment.status == "succeeded":
                    raise _Abort("already_processed")
                existing_payment.status = "succeeded"
                amount = existing_payment.amount
            else:
                payment = Payments(
                    provider=provider,
                    external_id=external_id,
                    user_id=user_id,
                    amount=amount,
                    currency=EnvKeys.PAY_CURRENCY,
                    status="succeeded"
                )
                s.add(payment)

            # 2. Update the user's balance
            user = (await s.execute(
                select(User).where(User.telegram_id == user_id).with_for_update()
            )).scalars().one()

            user.balance += amount

            # 3. Create a transaction record
            operation = Operations(
                user_id=user_id,
                operation_value=amount,
                operation_time=datetime.now(timezone.utc)
            )
            s.add(operation)

            # Referral on top-up removed (ТЗ-07): rewards on Order.COMPLETED only.
            referrer_id = None

    except _Abort as e:
        return False, e.code

    except IntegrityError:
        # Lost the unique(provider, external_id) race — already credited once.
        return False, "already_processed"

    except Exception as e:
        await log_audit(
            "payment_failed",
            level="WARNING",
            user_id=user_id,
            resource_type="Payment",
            details=f"provider={provider}, amount={amount}, error={e}",
        )
        return False, "payment_error"

    safe_create_task(invalidate_user_cache(user_id))
    safe_create_task(invalidate_stats_cache())
    return True, "success"


async def checkout_cart_transaction(
        user_id: int, expected_total: int | None = None
) -> tuple[bool, str, list | None]:
    """
    Atomic cart checkout — purchase all items from user's cart in one transaction.
    Promo codes are read from cart_items.promo_code and validated at checkout time.

    A promo code is a single redemption, so it discounts a single line — the most
    expensive one it validly applies to. A code that applies to no line at all
    (expired, used up, bound to a different product) is simply dropped from that
    line; the cart view renders the same rule, so the two totals agree and the
    ``expected_total`` guard below catches any drift.

    ``expected_total`` is the total shown to the user on the confirmation dialog.
    If the price/sale changed in between, the recomputed total won't match and the
    checkout aborts with ``price_changed`` instead of silently charging a
    different amount.

    Returns: (success, message, list[purchase_data])
    """
    max_retries = 3
    for attempt in range(max_retries):
        outcome: tuple[bool, str, list | None] | None = None
        try:
            async with Database().session() as s:
                # 1. Lock user
                user = (await s.execute(
                    select(User).where(User.telegram_id == user_id).with_for_update()
                )).scalars().one_or_none()
                if not user:
                    raise _Abort("user_not_found")

                # 2. Get cart items
                cart_items = (await s.execute(
                    select(CartItems).where(CartItems.user_id == user_id)
                )).scalars().all()

                if not cart_items:
                    raise _Abort("cart_empty")

                # Lock all distinct goods up front in a deterministic order (by id)
                # so two concurrent checkouts with overlapping carts acquire the row
                # locks in the same order and cannot form an AB/BA deadlock cycle.
                item_ids = list({ci.item_id for ci in cart_items})
                goods_by_id = {
                    g.id: g for g in (await s.execute(
                        select(Goods).where(Goods.id.in_(item_ids))
                        .order_by(Goods.id).with_for_update()
                    )).scalars().all()
                }

                # 3. Resolve items, validate promos, calculate total
                purchases = []
                items_to_remove = []
                # code -> promo row, fetched and locked once per checkout even when
                # the same code sits on several cart lines.
                promos_by_code: dict[str, PromoCodes | None] = {}
                # promo id -> how many times this user has redeemed it (one lookup per promo).
                promo_usage_count: dict[int, int] = {}

                for ci in cart_items:
                    goods = goods_by_id.get(ci.item_id)

                    if not goods:
                        items_to_remove.append(ci.id)
                        continue

                    qty = ci.quantity

                    has_inf = bool(
                        (await s.execute(
                            select(ItemValues.id)
                            .where(
                                ItemValues.item_id == goods.id,
                                ItemValues.is_infinity.is_(True),
                            )
                            .limit(1)
                        )).first()
                    )
                    if not has_inf and await count_finite_available_units(s, goods.id) == 0:
                        items_to_remove.append(ci.id)
                        continue

                    try:
                        delivered = await consume_stock_units(s, goods, qty)
                    except StockAllocationError as exc:
                        raise _Abort(exc.code)
                    values_to_delete = []

                    # Sale price is the authoritative base; promo stacks on top.
                    price, _on_sale, _original_price = effective_price(goods)
                    line_price = price * qty

                    # Resolve the promo for this line. A code that does not apply
                    # (expired, used up, bound to another product) is dropped from the line
                    promo = None
                    if ci.promo_code:
                        code = ci.promo_code.upper()
                        if code not in promos_by_code:
                            promos_by_code[code] = (await s.execute(
                                select(PromoCodes).where(PromoCodes.code == code).with_for_update()
                            )).scalars().first()
                        candidate = promos_by_code[code]
                        if candidate is not None:
                            if candidate.id not in promo_usage_count:
                                from bot.database.methods.promo_usage import (
                                    count_promo_usages_for_user,
                                )

                                promo_usage_count[candidate.id] = (
                                    await count_promo_usages_for_user(
                                        s, candidate.id, user_id
                                    )
                                )
                            max_per_user = int(
                                getattr(candidate, "max_uses_per_user", 1) or 1
                            )
                            used_up = promo_usage_count[candidate.id] >= max_per_user
                            if not await promo_rule_error(
                                s,
                                candidate,
                                user_id,
                                goods=goods,
                                used=used_up,
                                order_total_cents=line_price,
                            ):
                                promo = candidate

                    purchases.append({
                        'cart_id': ci.id,
                        'goods': goods,
                        'qty': qty,
                        'unit_price': price,
                        'line_price': line_price,
                        'promo': promo,
                        'delivered': delivered,
                        'values_to_delete': values_to_delete,
                    })

                promos_to_record: dict[int, PromoCodes] = {}
                for promo in {
                    p['promo'].id: p['promo'] for p in purchases if p['promo'] is not None
                }.values():
                    eligible = [p for p in purchases if p['promo'] is not None and p['promo'].id == promo.id]
                    best = max(eligible, key=lambda p: (p['line_price'], -p['cart_id']))
                    for p in eligible:
                        if p is not best:
                            p['promo'] = None
                    # Percent scales with quantity; fixed comes off the line once. Clamped so a bad discount can't go negative.
                    best['line_price'] = apply_promo_discount(
                        best['unit_price'], promo.discount_type, promo.discount_value, best['qty']
                    )
                    promos_to_record[promo.id] = promo

                for p in purchases:
                    # The line total is authoritative; per-unit prices are derived from it so the BoughtGoods rows sum back to what is charged.
                    p['unit_prices'] = _split_amount(p['line_price'], p['qty'])

                total_price = sum(p['line_price'] for p in purchases)

                # Remove invalid cart items
                if items_to_remove:
                    await s.execute(
                        sa_delete(CartItems).where(CartItems.id.in_(items_to_remove))
                    )

                if not purchases:
                    # Commit the invalid-item cleanup above, but report failure.
                    outcome = (False, "cart_items_unavailable", None)
                else:
                    # Guard: the sale/price (or a promo) may have changed between the confirmation dialog and this commit.
                    # Refuse to charge a total the user did not agree to.
                    if expected_total is not None and total_price != expected_total:
                        raise _Abort("price_changed")

                    # 4. Check balance
                    if user.balance < total_price:
                        raise _Abort("insufficient_funds")

                    # 5. Process each purchase — one BoughtGoods row per delivered
                    #    unit, each carrying its own value.
                    results = []
                    for p in purchases:
                        for v in p['values_to_delete']:
                            await s.delete(v)

                        for value, unit_price in zip(p['delivered'], p['unit_prices']):
                            bought_item = BoughtGoods(
                                item_name=p['goods'].name,
                                value=value,
                                price=unit_price,
                                buyer_id=user_id,
                                bought_datetime=datetime.now(timezone.utc),
                                unique_id=uuid4().int >> 65
                            )
                            s.add(bought_item)
                            await s.flush()
                            results.append({
                                "item_name": p['goods'].name,
                                "value": value,
                                "price": cents_to_float_rub(unit_price),
                                "bought_id": bought_item.id,
                                "unique_id": bought_item.unique_id,
                                "bought_datetime": bought_item.bought_datetime.isoformat(),
                            })

                    # 6. Record promo usage (once per distinct promo)
                    from bot.database.methods.promo_usage import (
                        PromoUsageLimitError,
                        record_promo_usage,
                    )

                    for promo in promos_to_record.values():
                        try:
                            await record_promo_usage(s, promo, user_id)
                        except PromoUsageLimitError:
                            raise _Abort("transaction_error")

                    # 7. Deduct total
                    user.balance -= total_price

                    # 8. Clear cart
                    await s.execute(
                        sa_delete(CartItems).where(CartItems.user_id == user_id)
                    )

                    outcome = (True, "success", results)

        except _Abort as e:
            return False, e.code, None

        except IntegrityError as e:
            if "unique_id" in str(e).lower() and attempt < max_retries - 1:
                continue  # Retry with new unique_ids
            await log_audit(
                "cart_checkout_failed",
                level="WARNING",
                user_id=user_id,
                details=str(e),
            )
            return False, "transaction_error", None

        except (OperationalError, DBAPIError) as e:
            msg = str(e).lower()
            # Postgres aborts one transaction in a deadlock/serialization cycle;
            # the victim is safe to retry (lock goods deterministically now).
            if (("deadlock" in msg or "could not serialize" in msg)
                    and attempt < max_retries - 1):
                continue
            await log_audit(
                "cart_checkout_failed",
                level="WARNING",
                user_id=user_id,
                details=str(e),
            )
            return False, "transaction_error", None

        except Exception as e:
            await log_audit(
                "cart_checkout_failed",
                level="WARNING",
                user_id=user_id,
                details=str(e),
            )
            return False, "transaction_error", None

        # Clean commit. Invalidate caches only on a successful checkout.
        if outcome[0]:
            safe_create_task(invalidate_user_cache(user_id))
            safe_create_task(invalidate_stats_cache())
            for name in {r["item_name"] for r in outcome[2]}:
                safe_create_task(invalidate_item_cache(name))
        return outcome

    return False, "transaction_error", None


async def replace_item_stock_and_meta(
        old_name: str,
        new_name: str,
        description: str,
        price,
        category_name: str,
        values: list[str],
        is_infinity: bool,
) -> tuple[bool, str | None, int]:
    """Swap a position's whole stock and its metadata in one transaction.

    Returns ``(success, error_code, values_added)``
    """
    from bot.database.methods.create import normalize_values
    normalized, _skipped_dup, _skipped_invalid = normalize_values(values)

    try:
        async with Database().session() as s:
            goods = (await s.execute(
                select(Goods).where(Goods.name == old_name).with_for_update()
            )).scalars().one_or_none()
            if not goods:
                raise _Abort("position_invalid")

            category_id = (await s.execute(
                select(Categories.id).where(Categories.name == category_name)
            )).scalar()
            if not category_id:
                raise _Abort("position_invalid")

            if new_name != old_name:
                clash = (await s.execute(
                    select(Goods.id).where(Goods.name == new_name)
                )).scalar()
                if clash:
                    raise _Abort("position_exists")

            # Resolve the old category's name before mutating: if the position moves, that category's cached item list/count is now stale too.
            old_category_name = (await s.execute(
                select(Categories.name).where(Categories.id == goods.category_id)
            )).scalar()

            # 1. Purge the current stock.
            await s.execute(sa_delete(ItemValues).where(ItemValues.item_id == goods.id))

            # 2. Insert the replacement stock. An infinite position holds exactly one row that is never consumed, so only the first value counts.
            to_insert = normalized[:1] if is_infinity else normalized
            for v in to_insert:
                from bot.catalog.enums import StockUnitStatus

                s.add(
                    ItemValues(
                        item_id=goods.id,
                        value=v,
                        is_infinity=is_infinity,
                        status=StockUnitStatus.AVAILABLE,
                    )
                )

            # 3. Update the metadata.
            goods.name = new_name
            goods.description = description
            goods.price = rub_to_cents(price)
            goods.category_id = category_id

            if new_name != old_name:
                # Purchase history denormalizes the name, so carry the rename over.
                await s.execute(
                    sa_update(BoughtGoods).where(BoughtGoods.item_name == old_name)
                    .values(item_name=new_name)
                )

            added = len(to_insert)

    except _Abort as e:
        return False, e.code, 0

    except Exception as e:
        await log_audit(
            "replace_item_stock_failed",
            level="WARNING",
            resource_type="Item",
            resource_id=old_name,
            details=str(e),
        )
        return False, "db_error", 0

    # Only after the commit: both names, and both categories when the position moved.
    for name in {old_name, new_name}:
        safe_create_task(invalidate_item_cache(name))
    for cat in {category_name, old_category_name} - {None}:
        safe_create_task(invalidate_category_cache(cat))
    safe_create_task(invalidate_stats_cache())

    return True, None, added


async def admin_balance_change(telegram_id: int, amount: int) -> tuple[bool, str]:
    """
    Atomic admin balance change (top-up or deduction) with operation record.
    amount > 0 for top-up, amount < 0 for deduction.
    Returns (success, message).
    """
    try:
        async with Database().session() as s:
            user = (await s.execute(
                select(User).where(User.telegram_id == telegram_id).with_for_update()
            )).scalars().one_or_none()

            if not user:
                raise _Abort("user_not_found")

            if amount < 0 and user.balance < abs(amount):
                raise _Abort("insufficient_funds")

            user.balance += amount

            operation = Operations(
                user_id=telegram_id,
                operation_value=amount,
                operation_time=datetime.now(timezone.utc)
            )
            s.add(operation)

    except _Abort as e:
        return False, e.code

    except Exception as e:
        await log_audit(
            "admin_balance_change_failed",
            level="WARNING",
            user_id=telegram_id,
            resource_type="User",
            details=f"amount={amount}, error={e}",
        )
        return False, "balance_change_error"

    safe_create_task(invalidate_user_cache(telegram_id))
    safe_create_task(invalidate_stats_cache())

    return True, "success"


async def redeem_balance_promo(code: str, user_id: int) -> tuple[bool, str, int | None]:
    """
    Redeem a balance-type promo code: add discount_value to user balance.
    Returns (success, error_key_or_empty, amount_added).
    """
    try:
        async with Database().session() as s:
            user = (await s.execute(
                select(User).where(User.telegram_id == user_id).with_for_update()
            )).scalars().one_or_none()
            if not user:
                raise _Abort("promo.not_found")

            promo = (await s.execute(
                select(PromoCodes).where(PromoCodes.code == code.upper()).with_for_update()
            )).scalars().first()

            err = await promo_rule_error(s, promo, user_id, require_balance=True)
            if err:
                raise _Abort(_REDEEM_PROMO_ERRORS[err])

            amount = int(promo.discount_value)
            user.balance += amount
            from bot.database.methods.promo_usage import (
                PromoUsageLimitError,
                record_promo_usage,
            )

            try:
                await record_promo_usage(s, promo, user_id)
            except PromoUsageLimitError as exc:
                raise _Abort(_REDEEM_PROMO_ERRORS[exc.code])
            s.add(Operations(
                user_id=user_id,
                operation_value=amount,
                operation_time=datetime.now(timezone.utc),
            ))

    except _Abort as e:
        return False, e.code, None

    except Exception as e:
        await log_audit(
            "promo_redeem_failed",
            level="WARNING",
            user_id=user_id,
            resource_type="PromoCode",
            resource_id=code,
            details=str(e),
        )
        return False, "errors.something_wrong", None

    safe_create_task(invalidate_user_cache(user_id))
    safe_create_task(invalidate_stats_cache())
    return True, "", amount
