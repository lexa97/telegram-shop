"""ТЗ-13: сценарии §20 исходного ТЗ привязаны к существующим автотестам."""

import importlib
from typing import Optional

import pytest

# mod, optional class, test function name
_SECTION_20: list[tuple[str, str, Optional[str], str]] = [
    ("20.1", "tests.test_user_handlers", "TestStartHandler", "test_start_creates_new_user"),
    ("20.1b", "tests.test_user_handlers", "TestStartHandler", "test_start_with_referral"),
    ("20.2", "tests.test_platega_payments", "TestPlategaGateway", "test_webhook_credits_balance_once"),
    ("20.2b", "tests.test_transactions", "TestProcessPaymentWithReferral", "test_payment_idempotency"),
    ("20.3", "tests.test_fulfillment_tz06", None, "test_stock_purchase_creates_completed_order"),
    ("20.4", "tests.test_fulfillment_tz06", None, "test_two_buyers_one_key"),
    ("20.5", "tests.test_fulfillment_tz06", None, "test_api_fake_completes_with_delivery"),
    ("20.6", "tests.test_fulfillment_tz06", None, "test_api_timeout_then_success_one_external_order"),
    ("20.7", "tests.test_fulfillment_tz06", None, "test_api_timeout_then_success_one_external_order"),
    ("20.8", "tests.test_fulfillment_tz06", None, "test_api_fatal_refunds_balance"),
    ("20.9", "tests.test_fulfillment_tz06", None, "test_api_fatal_refunds_balance"),
    ("20.10", "tests.test_workers_tz12", None, "test_concurrent_fulfill_single_external_order"),
    ("20.11", "tests.test_promo_referral_tz07", None, "test_redeem_last_use_race_parallel"),
    ("20.12", "tests.test_promo_referral_tz07", None, "test_referral_on_completed_order"),
    ("20.12b", "tests.test_promo_referral_tz07", None, "test_topup_no_referral_earnings"),
    ("20.13", "tests.test_workers_tz12", None, "test_worker_expire_created_releases_stock"),
    ("20.14", "tests.test_rbac_tz08", None, "test_builtin_role_masks"),
    ("20.14b", "tests.test_rbac_tz08", None, "test_operator_console_hides_roles_and_balance"),
    ("20.15", "tests.test_rbac_tz08", None, "test_order_refund_writes_audit"),
]


@pytest.mark.parametrize(
    "section,mod_name,cls_name,func_name",
    _SECTION_20,
    ids=[row[0] for row in _SECTION_20],
)
def test_section_20_autotest_registered(section, mod_name, cls_name, func_name):
    mod = importlib.import_module(mod_name)
    if cls_name:
        cls = getattr(mod, cls_name)
        assert callable(getattr(cls, func_name))
    else:
        assert callable(getattr(mod, func_name))
