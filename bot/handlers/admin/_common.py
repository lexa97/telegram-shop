from decimal import Decimal, InvalidOperation
from html import escape as _esc

from bot.i18n import localize
from bot.logger_mesh import logger
from bot.misc import EnvKeys
from bot.money import format_cents_for_ui

# Max ruble amount for a catalog price (stored as kopecks in DB).
MAX_ITEM_PRICE_RUB = Decimal("99999999.99")


def parse_price(text: str) -> str | None:
    """Parse a catalog price in rubles (up to 2 decimal places). None if invalid.

    Returns a normalized decimal string for FSM storage (e.g. ``"199.99"``, ``"100"``).
    """
    price_text = (text or "").strip().replace(",", ".")
    if not price_text or not price_text.replace(".", "", 1).isdigit():
        return None
    try:
        amount = Decimal(price_text)
    except InvalidOperation:
        return None
    if amount.as_tuple().exponent < -2:
        return None
    if amount <= 0 or amount > MAX_ITEM_PRICE_RUB:
        return None
    return format(amount, "f")


async def _notify_restock_safe(bot, item_name: str) -> None:
    """Fire restock notifications, never letting a failure break the stock add."""
    from bot.misc.services.restock_notifier import notify_restock
    try:
        await notify_restock(bot, item_name)
    except Exception:
        logger.exception("restock notification failed for %r", item_name)


def user_profile_lines(user, first_name, target_id, *, overall_balance,
                       items_count, role, referrals, include_referral_id):
    """Build the common user-profile text lines shared by the admin profile views.

    Returns a list of lines (join with ``"\n"``). ``include_referral_id`` inserts
    the referral_id line — the read-only show-user view includes it, the
    action-panel view does not. Callers append their own extra lines afterward
    (blocked status, earnings stats).
    """
    lines = [
        localize('profile.caption', name=_esc(str(first_name or '')), id=target_id),
        '',
        localize('profile.id', id=target_id),
        localize('profile.balance', amount=format_cents_for_ui(int(user.get('balance') or 0)), currency=EnvKeys.PAY_CURRENCY),
        localize('profile.total_topup', amount=format_cents_for_ui(int(overall_balance)), currency=EnvKeys.PAY_CURRENCY),
        localize('profile.purchased_count', count=items_count),
        '',
    ]
    if include_referral_id:
        lines.append(localize('profile.referral_id', id=user.get('referral_id')))
    lines += [
        localize('admin.users.referrals', count=referrals),
        localize('admin.users.role', role=role),
        localize('profile.registration_date', dt=user.get('registration_date')),
    ]
    return lines
