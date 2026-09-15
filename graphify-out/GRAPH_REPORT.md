# Graph Report - workspace  (2026-09-15)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2854 nodes · 7640 edges · 154 communities (124 shown, 15 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 542 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d1b8facb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 150
- Community 151

## God Nodes (most connected - your core abstractions)
1. `Database` - 274 edges
2. `localize()` - 225 edges
3. `back()` - 112 edges
4. `log_audit()` - 78 edges
5. `LazyPaginator` - 54 edges
6. `add_to_cart()` - 52 edges
7. `_make_promo()` - 50 edges
8. `buy_item_transaction()` - 49 edges
9. `safe_create_task()` - 45 edges
10. `esc()` - 45 edges

## Surprising Connections (you probably didn't know these)
- `db_cleanup()` --uses--> `Database`  [INFERRED]
  tests/conftest.py → bot/database/main.py
- `setup_test_database()` --uses--> `Database`  [INFERRED]
  tests/conftest.py → bot/database/main.py
- `user_factory()` --uses--> `Database`  [INFERRED]
  tests/conftest.py → bot/database/main.py
- `TestStatsAggregates` --uses--> `Database`  [INFERRED]
  tests/test_admin_handlers.py → bot/database/main.py
- `TestAuditBuffer` --uses--> `Database`  [INFERRED]
  tests/test_audit.py → bot/database/main.py

## Import Cycles
- None detected.

## Communities (154 total, 15 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (75): check_value_cached(), has_purchased_item(), invalidate_rating_cache(), Cached check_value (whether the item has an infinite value)., Check if user has purchased an item., Invalidate the review caches for an item (average and count)., apply_promo_handler(), back_to_item_handler() (+67 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (43): AuthenticationBackend, get_item_name_by_id(), Return a product's name by its id, or None. ItemValues.item is lazy='raise', so…, get_metrics(), Getting a global metrics collector, AdminAuth, AuditLogAdmin, AuditModelView (+35 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (57): AsyncEngine, Database, Async contextual session: guaranteed to close/rollback on error., Dispose of the connection pool., create_review(), Create a review. Returns ID, or None if the item is unknown, already reviewed,…, clear_cart(), delete_review() (+49 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (50): check_role_name_by_id(), _day_window(), get_all_users(), get_blocked_user_ids(), get_category_name_by_id(), get_roles_with_user_counts(), datetime, Decimal (+42 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (38): _on_task_done(), Any, Safely create an async task for cache invalidation. Works in two contexts: 1.…, safe_create_task(), _add_to_cart_once(), create_category(), create_item(), normalize_values() (+30 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (48): get_user_profile_aggregates(), Everything the admin user-profile screen needs, in one query., Build the common user-profile text lines shared by the admin profile views.…, user_profile_lines(), admin_all_earnings_pagination_handler(), admin_earning_detail_handler(), admin_ref_earnings_pagination_handler(), admin_referral_earnings_handler() (+40 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (31): _finalize_promo_creation(), navigate_promos(), promo_binding_type_chosen(), promo_create_start(), _promo_list_label(), promo_management_handler(), promo_receive_binding_name(), promo_receive_code() (+23 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (33): add_item_callback_handler(), add_item_description(), add_item_price(), adding_value_to_position(), check_category_for_add_item(), collect_item_value(), finish_adding_item_callback_handler(), finish_adding_items_callback_handler() (+25 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (12): Validate a promo code for a specific item and user. Returns (valid, error_key,…, validate_promo_for_item(), buy_item_transaction(), Complete transactional purchase of goods with checks and locks. Returns:…, _goods(), _make_promo(), The fix must not turn every unscoped promo into a rejection., scope (applicability) and discount_type (value) are orthogonal axes.… (+4 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (28): BoughtGoods, User, _check_auth(), export_operations(), export_payments(), export_purchases(), export_users(), _parse_date_params() (+20 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (34): async_cached(), decorator(), async_wrapper(), get_user_count_cached(), Decorator for async functions with caching. Misses are single-flighted (see…, Cached quantity of goods, Cached number of users, select_item_values_amount_cached() (+26 more)

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (40): add_category_callback_handler(), categories_callback_handler(), delete_category_callback_handler(), callback_query, CallbackQuery, Asks admin for current category name before renaming., Opens the categories management submenu., Asks admin for a new category name. (+32 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (18): AnalyticsMiddleware, init_metrics(), MetricsCollector, _prom_label(), Any, Exporting metrics in Prometheus format, Middleware for analytics collection, Return a label value safe to interpolate into the exposition format. (+10 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (37): get_items_info(), _obj_to_dict(), Return {name: item_row_dict} for the given names in a single query., Convert an ORM object to a dict of its column values., Batch counterpart of validate_promo_for_item for a whole cart. Same verdicts,…, validate_promos_for_cart(), clear_cart_item_promo(), Drop the promo code from one cart line. Scoped by user_id so one user cannot… (+29 more)

### Community 14 - "Community 14"
Cohesion: 0.09
Nodes (13): add_values_bulk(), add_values_to_item(), Add a whole batch of stock values in one transaction. Returns ``(added,…, Add item value if not duplicate; True if inserted. Resolves item_name to…, get_item_info(), Return item (position) row as dict by name, or None., Return count of item_values for an item (by item name)., select_item_values_amount() (+5 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (28): logs_callback_handler(), navigate_users(), callback_query, CallbackQuery, FSMContext, Render one page of the all-users list (shared by the view and paginate…, Show list of all users with lazy loading pagination., Pagination for users list with lazy loading. (+20 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (31): drain_background_tasks(), Wait for in-flight fire-and-forget tasks to finish. Called during shutdown so a…, Seed the built-in roles (USER/ADMIN/OWNER)., register_models(), configure_logging(), _queued_file_handler(), Stop file-log listeners, flushing anything still queued., A QueueHandler in front of a RotatingFileHandler. File writes are synchronous;… (+23 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (25): _notify_restock_safe(), parse_price(), Parse an item price from admin input. None if it is not a usable price., Fire restock notifications, never letting a failure break the stock add., check_item_name_for_update(), message, Starts the full update flow., Validate item and ask for a new name. (+17 more)

### Community 18 - "Community 18"
Cohesion: 0.15
Nodes (18): add_to_cart(), Add `quantity` units of an item to the user's cart. One row per (user, item):…, promo_rule_error(), Shared promo-code business rules; returns a canonical error code or None if…, checkout_cart_transaction(), Atomic cart checkout — purchase all items from user's cart in one transaction.…, PromoCodeUsages, Covers the per-cart-line call in checkout_cart_transaction. A promo whose… (+10 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (25): create_promo_code(), Create a promo code. Returns ID or None if code already exists. Raises…, delete_promo_code(), Delete a promo code by ID., get_promo_code(), Return promo code by code string, or None., Toggle promo code active status. Returns new is_active or None if not found., toggle_promo_code() (+17 more)

### Community 20 - "Community 20"
Cohesion: 0.11
Nodes (28): apply_promo_discount(), coerce_sale_until(), effective_price(), _get(), Any, datetime, Decimal, Normalize a sale_until value to a timezone-aware datetime (or None). Product… (+20 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (14): AsyncSession, Base, Typed declarative base (SQLAlchemy 2.0) shared by all ORM models., get_audit_buffer(), log_audit(), log_audit_bg(), The process-wide audit buffer (started at boot, drained on shutdown)., Write audit entry to both the log file and the database. When 'session' is… (+6 more)

### Community 22 - "Community 22"
Cohesion: 0.06
Nodes (31): Adding stock from the web panel, Admin menu & shop management, 🎛️ Admin panel, 🏗️ Architecture, Broadcast, statistics & monitoring, Browsing the shop, Cart, Categories & products (+23 more)

### Community 23 - "Community 23"
Cohesion: 0.09
Nodes (13): CacheManager, Any, Delete a value from the cache, Centralized caching manager with graceful Redis degradation, Delete several keys in a single round-trip. The invalidation helpers drop 5-6…, Ping Redis and restore healthy status if connection is back., Invalidate all keys by pattern, Replay invalidations that were deferred while Redis was down. Called from… (+5 more)

### Community 24 - "Community 24"
Cohesion: 0.14
Nodes (16): check_value(), Return True if item has any infinite value (is_infinity=True)., callback_query, CallbackQuery, Handle infinity decision: - change_*_no -> just update meta without changing…, Switch to regular (non-infinite) mode: - accumulate values, - then apply…, Finalize switch to regular mode: replace the stock with the collected values…, update_item_no_infinity() (+8 more)

### Community 25 - "Community 25"
Cohesion: 0.12
Nodes (14): cache_result(), Decorator for caching function results. Misses are single-flighted: when a hot…, Any, Cached global statistics., Re-hydrate money fields a Redis round-trip turned into strings, The rest of the admin statistics screen, in one query, Warming up the cache at startup, Specialized cache for statistics (+6 more)

### Community 26 - "Community 26"
Cohesion: 0.12
Nodes (11): LazyPaginator, Args: query_func: Function to query data (offset, limit) -> List per_page:…, Get the total number of items, Get the data for the page Args: page: Page number (starting from 0) Returns:…, Paginator with lazy loading of data from database. Scoped to a single render:…, Get total number of pages, _empty_query(), _mock_query() (+3 more)

### Community 27 - "Community 27"
Cohesion: 0.09
Nodes (20): CategoryFSM, StatesGroup, FSM states for category management: - add, - delete, - rename., FSM for setting or removing a time-limited sale on an item: 1) item name, 2)…, SaleFSM, BalanceStates, StatesGroup, FSM states for the balance top-up flow. (+12 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (27): category_factory(), _create(), item_factory(), _create(), make_callback_query(), _make(), make_message(), _make() (+19 more)

### Community 29 - "Community 29"
Cohesion: 0.09
Nodes (12): get_all_roles(), Return role_id with the highest numeric permissions value (OWNER=127)., Return all roles as list of dicts ordered by permissions asc., select_max_role_id(), _perms_done(), message, role_create_name(), role_edit_name() (+4 more)

### Community 30 - "Community 30"
Cohesion: 0.12
Nodes (12): get_cart_count(), get_cart_items(), Return all cart items for user; each dict includes the current item_name for…, Return the total number of units in a user's cart. Units, not lines: this feeds…, Apply `delta` to a cart line's quantity. Dropping to zero or below removes the…, set_cart_item_quantity(), The unique constraint is what makes a cart line == one position., The cart caps *distinct* positions, not units. (+4 more)

### Community 31 - "Community 31"
Cohesion: 0.10
Nodes (13): Register the rate-limit middleware (shares the auth role cache)., _setup_rate_limiting(), RateLimitConfig, RateLimiter, Configuration for rate limiting, A repository for tracking rate limits, Connects rate limiting to the dispatcher, Clears old requests outside the window (+5 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (17): create_user(), datetime, Create user if missing; commit., Operations, ReferralEarnings, operation_factory(), Seed a balance Operations row (see tests/factories.py)., Seed a ReferralEarnings row (see tests/factories.py). (+9 more)

### Community 33 - "Community 33"
Cohesion: 0.12
Nodes (18): _any_payment_method_enabled(), Is there at least one enabled payment method?, _notify_referrer_bonus(), pre_checkout_handler(), Decimal, Send referral bonus notification to the referrer if applicable., Validate the payment before Telegram processes it., Handle successful payment: - XTR (Stars): total_amount is ⭐. take CURRENCY from… (+10 more)

### Community 34 - "Community 34"
Cohesion: 0.10
Nodes (15): check_suspicious_patterns(), Any, BaseMiddleware, TelegramObject, Checking for suspicious patterns in callback data, Getting a user role with caching. See resolve_role_cached., Middleware for additional security: - Audit logging for critical operations -…, Checking whether an action is critical (+7 more)

### Community 35 - "Community 35"
Cohesion: 0.11
Nodes (12): check_role(), check_user_cached(), count_users_with_role(), get_role_id_by_name(), Return count of users assigned to a given role., Cached version of check_user, Return permission bitmask for user (0 if none)., Return role id by name or None. (+4 more)

### Community 36 - "Community 36"
Cohesion: 0.12
Nodes (10): create_role(), Create a new role. Returns the new role ID, or None if name conflict., delete_role(), Delete a role. Fails if users are assigned, it's default, or it's a built-in…, get_role_by_id(), Return single role as dict or None., Update role name and permissions. Returns (success, error_message)., update_role() (+2 more)

### Community 37 - "Community 37"
Cohesion: 0.12
Nodes (16): check_category_cached(), Cached Category Check, check_category_for_update(), check_category_name_for_update(), process_category_for_add(), process_category_for_delete(), message, Verifies the category exists, then prompts for a new name. (+8 more)

### Community 38 - "Community 38"
Cohesion: 0.12
Nodes (16): update_progress(), cancel_broadcast_handler(), _cancel_keyboard(), callback_query, CallbackQuery, FSMContext, Cancel the caller's current mailing., Progress-message keyboard with a working cancel button. (+8 more)

### Community 39 - "Community 39"
Cohesion: 0.11
Nodes (10): AuthenticationMiddleware, Middleware for authentication and authorization verification, Remove cached role for a user so permissions are re-fetched., Load the blocked-user set from DB; on success it becomes authoritative., Load blocked users from DB into memory cache on startup., setter, _auth_callback(), A CallbackQuery mock that passes the middleware's isinstance checks. (+2 more)

### Community 40 - "Community 40"
Cohesion: 0.14
Nodes (14): BaseFilter, Permission, True if every bit in `bit` is set in `perms` (same AND semantics as…, HasAnyPermissionFilter, HasPermissionFilter, CallbackQuery, Message, Validation of the replenishment amount (used in FSM steps). (+6 more)

### Community 41 - "Community 41"
Cohesion: 0.16
Nodes (15): get_goods_info(), Return item_value row as dict by id, including item_name from Goods., item_info_callback_handler(), process_delete_item_from_position(), FSMContext, Shows details for a specific item within a position. Callback data format:…, Delete item from position and refresh the list with lazy loading. Callback data…, _callbacks() (+7 more)

### Community 42 - "Community 42"
Cohesion: 0.16
Nodes (13): ItemPurchaseRequest, Validate and convert telegram ID, Validate money amount, Escape text, then re-enable a small set of formatting tags., Validate item purchase request, sanitize_html(), validate_money_amount(), validate_telegram_id() (+5 more)

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (16): delete_category(), Delete a category and all products/stock inside it (CASCADE handles items)., check_category(), _fetch_one_dict(), get_bought_item_info(), Return bought item row as dict by row id, or None. When ``buyer_id`` is given…, Return category as dict by name, or None., Return one bought item by unique_id as dict, or None. (+8 more)

### Community 44 - "Community 44"
Cohesion: 0.11
Nodes (10): query_goods_search(), Search goods by name or description with pagination. Returns a list of names,…, Render one page of search results. `target` is a CallbackQuery or Message., receive_search_query_handler(), _show_search_page(), Proves the OR arm against description, not just name., Back from a search-opened card must return to the results, not categories., LIKE wildcards typed by a user must be literals, not patterns. (+2 more)

### Community 45 - "Community 45"
Cohesion: 0.15
Nodes (12): check_user(), Return user by Telegram ID or None if not found., _delete_quietly(), Message, Delete a message, tolerating the cases Telegram refuses. A message older than…, Handle /start: - Ensure user exists (register if new) - (Optional) Check…, start(), TestReplenishBalance (+4 more)

### Community 46 - "Community 46"
Cohesion: 0.11
Nodes (12): check_user_referrals(), get_one_referral_earning(), get_referral_earnings_stats(), get_user_referral(), Return count of referrals of the user., Return referral_id of the user or None., Get statistics on user referral charges., Get one referral earning as a dict, or None. When ``referrer_id`` is given the… (+4 more)

### Community 47 - "Community 47"
Cohesion: 0.13
Nodes (6): process_payment_with_referral(), Processing a payment with a referral bonus in one transaction. Returns…, Payments, Test that DB mutation functions trigger the correct cache invalidation., TestCacheInvalidationAfterMutations, TestProcessPaymentWithReferral

### Community 48 - "Community 48"
Cohesion: 0.15
Nodes (16): console_callback_handler(), callback_query, CallbackQuery, FSMContext, Admin menu (only for admins and above)., Toggle maintenance mode on/off., toggle_maintenance_handler(), _drop_redis_role() (+8 more)

### Community 49 - "Community 49"
Cohesion: 0.20
Nodes (19): _parse_channel_username(), Extract channel username from CHANNEL_URL env variable., back_to_menu_callback_handler(), check_sub_to_channel(), _ensure_user(), navigate_operations(), operation_history_handler(), profile_callback_handler() (+11 more)

### Community 50 - "Community 50"
Cohesion: 0.12
Nodes (8): invalidate_user_cache(), Invalidate a user's cached row, role and paginator counts. Batched into one…, :count is the only key in the category_items namespace, so this runs on named…, The operations history counts a UNION over three tables; the paginator asks for…, Test that each invalidation function removes the expected keys., This runs on every purchase/payment/checkout, so it must stay on targeted…, TestCacheInvalidationFunctions, _record()

### Community 51 - "Community 51"
Cohesion: 0.13
Nodes (9): create_pending_payment(), Create pending payment., TestPayments, API timeout should not crash the recovery manager., Active (not yet paid/expired) payment should stay pending., Non-cryptopay payments should be skipped., The per-minute health check must not spend a Telegram API call — polling…, A failing pass must back off and be retried, not kill the task. (+1 more)

### Community 52 - "Community 52"
Cohesion: 0.18
Nodes (9): Subscribe a user to the restock notification for an item. Idempotent:…, subscribe_to_stock(), pop_stock_subscribers(), Claim and remove every restock subscription for an item. Locks the rows before…, is_subscribed_to_stock(), Whether the user is waiting for this item to be restocked., The property that stops two concurrent restocks messaging twice., TestStockSubscriptions (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.31
Nodes (18): check_role_cached(), Cached permission bitmask for a user. Delegates to the shared role cache in the…, True if every bit in `perms` is also set in `of`., assign_role_list(), callback_query, CallbackQuery, FSMContext, role_create_start() (+10 more)

### Community 54 - "Community 54"
Cohesion: 0.16
Nodes (7): _calc_cart_total_with_promos(), Calculate real cart total considering sales and promo codes on each item., The discount the cart actually renders for this line, or None. Goes through…, A balance promo has no product to apply to. The old code only checked…, The checkout confirmation total must not promise a discount either., The confirmation dialog and the charge must pick the same line., TestCartDisplayMatchesCheckout

### Community 55 - "Community 55"
Cohesion: 0.12
Nodes (9): Disaster Recovery Manager — payment recovery and health monitoring, Mark payment as failed., One DB + cache health probe, Starting the recovery system, Stopping the recovery system, Run one pass of `step` every `interval` seconds until stopped, One sweep over CryptoPay payments left pending for over an hour., Verification and processing of a specific payment. Args: payment: dict with… (+1 more)

### Community 56 - "Community 56"
Cohesion: 0.18
Nodes (4): The single-round-trip check() must reach the same verdicts as the four separate…, Order is load-bearing: the global window is recorded before the action window…, TestCombinedCheck, TestRedisRateLimiter

### Community 57 - "Community 57"
Cohesion: 0.14
Nodes (12): BaseModel, PaymentRequest, PromoCodeRequest, Decimal, Validate review input, Validate user data updates, Validate payment request data, Validate promo code input (+4 more)

### Community 58 - "Community 58"
Cohesion: 0.20
Nodes (9): Redeem a balance-type promo code: add discount_value to user balance. Returns…, redeem_balance_promo(), _future(), _mark_used(), _past(), datetime, The batch validator must give the same verdicts as validate_promo_for_item., TestBatchCartPromoValidation (+1 more)

### Community 59 - "Community 59"
Cohesion: 0.14
Nodes (13): buy_item_callback_handler(), invalid_amount(), CallbackQuery, FSMContext, message, Processing the purchase of goods with full transactional security., Ask user for the amount if at least one payment method is enabled., Store amount and show payment methods. (+5 more)

### Community 60 - "Community 60"
Cohesion: 0.17
Nodes (9): get_locale(), clear_locale_cache(), fixture, parametrize, get_locale is lru_cached — every case needs a cold cache on both sides., Patch the configured locale for one call., TestGetLocale, TestLocalize (+1 more)

### Community 61 - "Community 61"
Cohesion: 0.18
Nodes (9): Any, BaseMiddleware, TelegramObject, RateLimitMiddleware, Middleware to limit the frequency of requests, Determines the action from the event, Checks if the user is an admin (delegates to AuthenticationMiddleware cache), Return the Redis-backed limiter when Redis is healthy, else None. Falls back to… (+1 more)

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (4): _FakeRedis, _run(), Trim the window, then record the request if it fits. True if allowed., Emulate whichever of the two Lua scripts was registered. Told apart by arity:…

### Community 63 - "Community 63"
Cohesion: 0.15
Nodes (9): Total of a user's operations, summed server-side (avoids pulling every row)., select_user_operations_total(), is_user_blocked(), Set user blocked status and commit., Check if user is blocked., set_user_blocked(), Block a user (saves to DB and memory cache), Unblock a user (saves to DB and removes from memory cache) (+1 more)

### Community 64 - "Community 64"
Cohesion: 0.16
Nodes (10): _Abort, admin_balance_change(), Decimal, Exception, Abort the current transaction with a user-facing failure code., Split `total` into `n` amounts that sum back to it exactly. A cart line is…, Atomic admin balance change (top-up or deduction) with operation record. amount…, _split_amount() (+2 more)

### Community 65 - "Community 65"
Cohesion: 0.22
Nodes (9): broadcast_messages(), message, Executing mailing with progress bar, clean_manager_registry(), fixture, broadcast_managers is module-level state shared across tests., A message whose .answer returns an editable progress message., sending_message() (+1 more)

### Community 66 - "Community 66"
Cohesion: 0.16
Nodes (9): generate_short_hash(), Generate a short hash for long strings to fit in callback_data, parametrize, File handlers must sit behind a QueueListener so disk writes never block the…, TestAnyPaymentMethodEnabled, TestCheckSubChannel, TestGenerateShortHash, TestIsSafeItemName (+1 more)

### Community 67 - "Community 67"
Cohesion: 0.18
Nodes (5): In-memory counterpart of RedisRateLimiter.check., Returns the wait time until the next available request, Distributed rate limiter backed by Redis (shared across processes). Uses one…, Run the whole rate-limit decision in one round-trip. Returns ``(verdict,…, RedisRateLimiter

### Community 68 - "Community 68"
Cohesion: 0.17
Nodes (9): CryptoPayAPI, CryptoPayAPIError, Exception, Exception raised when CryptoPay API returns an error., Minimal async client for Crypto Bot API used to create and fetch invoices., Create a Crypto Pay invoice for given fiat amount/currency., Fetch a single invoice by id., ClientSession (+1 more)

### Community 69 - "Community 69"
Cohesion: 0.26
Nodes (9): Set or clear a time-limited sale on a Goods item. Pass sale_percent/sale_until…, set_item_sale(), _create_promo(), _future(), _past(), datetime, _set_sale(), TestSalePurchase (+1 more)

### Community 70 - "Community 70"
Cohesion: 0.18
Nodes (8): check_user_data(), process_replenish_user_balance(), message, Validates ID and shows user profile directly., Processes entered amount and tops up user's balance., TestCheckUserData, TestReplenishBalanceEdgeCases, TestUpdateItemFlow

### Community 71 - "Community 71"
Cohesion: 0.17
Nodes (12): payment_menu(), profile_keyboard(), InlineKeyboardMarkup, question_buttons(), rating_keyboard(), Buttons under the invoice (CryptoPay, etc.)., Universal yes/no + Back., Rating selection keyboard (1-5 stars). (+4 more)

### Community 72 - "Community 72"
Cohesion: 0.20
Nodes (8): check_item_name_for_amount_upd(), Finish adding new item values., Starts the flow for adding values (stock) to an existing item., Validate that item exists and is NOT infinite. If item is infinite — values…, update_item_amount_callback_handler(), updating_item_amount(), An unlimited position has no per-unit stock to append to., TestRestockBranch

### Community 73 - "Community 73"
Cohesion: 0.24
Nodes (6): navigate_items_in_goods(), Paginates items inside a position with lazy loading. Callback data format:…, Shows all items in the selected position with lazy loading pagination., show_str_item(), TestNavigateItemsInPosition, TestShowItemsInPosition

### Community 74 - "Community 74"
Cohesion: 0.21
Nodes (8): close(), get_payment_choice(), Select a payment method., Universal button assembly from (text, callback_data), simple_buttons(), TestBackAndClose, TestGetPaymentChoice, TestSimpleButtons

### Community 75 - "Community 75"
Cohesion: 0.22
Nodes (3): CleanupManager, Periodic cleanup of old audit_log entries and expired payments., TestCleanupRetention

### Community 76 - "Community 76"
Cohesion: 0.14
Nodes (6): db_cleanup(), fake_cache(), FakeCacheManager, Clean all data between tests by deleting rows from all tables (except roles…, Dict-based cache that mirrors CacheManager's interface., Provide a FakeCacheManager and patch get_cache_manager everywhere.

### Community 77 - "Community 77"
Cohesion: 0.18
Nodes (3): get_user_count(), Return total users count., TestUserCRUD

### Community 78 - "Community 78"
Cohesion: 0.21
Nodes (10): delete_item_callback_handler(), goods_management_callback_handler(), callback_query, CallbackQuery, Opens the positions (goods) management menu., Requests a position name to delete., Requests a position name to show its items., show_items_callback_handler() (+2 more)

### Community 79 - "Community 79"
Cohesion: 0.18
Nodes (12): check_sub_channel(), close_callback_handler(), dummy_button(), callback_query, CallbackQuery, processing of message closure (deletion), “Empty” (dummy) button, channel subscription check (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.21
Nodes (7): main_menu(), _has_url_button(), parametrize, Check if any button has a URL., TestMainMenu, TestProfileKeyboard, TestReferralSystemKeyboard

### Community 81 - "Community 81"
Cohesion: 0.24
Nodes (4): notify_restock(), Bot, Tell everyone waiting on `item_name` that it is back, and unsubscribe them.…, TestRestockNotifier

### Community 82 - "Community 82"
Cohesion: 0.18
Nodes (8): BroadcastManager, Bot, InlineKeyboardMarkup, Perform broadcast to a list of users Args: user_ids: List of user IDs text:…, Cancel the current mailing, Manager for mass mailing with optimization, Args: bot: Bot instance batch_size: Number of messages in a batch batch_delay:…, Securely sending a message with error handling. Returns one of: "sent",…

### Community 83 - "Community 83"
Cohesion: 0.15
Nodes (12): 2026-09-15 — Подготовка окружения, Graphiti (граф по коду), Архитектура (суть), Как вести журнал, Как запустить (основное приложение), Контекст, Открытые вопросы, Память проекта (журнал работ) (+4 more)

### Community 85 - "Community 85"
Cohesion: 0.21
Nodes (6): ABC, EnvKeys, Whether the admin session cookie should be marked Secure., Check configuration: fatal on unsafe defaults, warnings otherwise., Secure environment configuration with validation, Whether the admin panel is bound somewhere off-host. Webhook mode counts as…

### Community 86 - "Community 86"
Cohesion: 0.21
Nodes (5): AuditBuffer, Collects audit rows and writes them out in batches. Buffering is only active…, Queue a row. False if the caller should write it through itself., Write everything buffered so far. Returns the number of rows written., Stop the flusher and write out whatever is still buffered.

### Community 87 - "Community 87"
Cohesion: 0.20
Nodes (7): get_item_info_cached(), Cached product information, delete_str_item(), message, Deletes a position by the provided name., TestGoodsManagement, TestDeletePosition

### Community 88 - "Community 88"
Cohesion: 0.18
Nodes (4): Role, Replace Database singleton with async SQLite in-memory engine for all tests., setup_test_database(), _setup()

### Community 89 - "Community 89"
Cohesion: 0.24
Nodes (5): checking_payment(), Check CryptoPay invoice status and credit balance if paid., Balance is NUMERIC(12,2): the kopecks of an invoice must survive., TestCheckingPayment, TestCryptoPayFractionalAmounts

### Community 90 - "Community 90"
Cohesion: 0.21
Nodes (8): admin_console_keyboard(), Admin panel — shows only buttons the user has permissions for., _all_button_texts(), _all_callback_data(), Extract all callback_data values from markup., Extract all button texts from markup., TestAdminConsoleKeyboard, TestQuestionButtons

### Community 91 - "Community 91"
Cohesion: 0.26
Nodes (5): item_info(), Product card with buy, cart, promo, review buttons. When `out_of_stock`, offers…, Telegram caps callback_data at 64 bytes; a 100-char Cyrillic product name…, TestCallbackDataFitsTelegramLimit, TestItemInfoKeyboard

### Community 92 - "Community 92"
Cohesion: 0.20
Nodes (7): Forget the cached instance so the next call constructs a fresh one. Used by the…, One instance per class using this metaclass., SingletonMeta, Validate search queries, Sanitize the search query, SearchQuery, type

### Community 93 - "Community 93"
Cohesion: 0.27
Nodes (7): currency_to_stars(), _minor_units_for(), Convert currency amount to integer number of Telegram Stars. round up (ceil) to…, Return multiplier to convert major units to minor units., parametrize, TestCurrencyToStars, TestMinorUnitsFor

### Community 94 - "Community 94"
Cohesion: 0.26
Nodes (10): clean_datetime_data(), _col_is_numeric(), constraint_exists(), downgrade(), index_exists(), Switch money to Numeric(12,2), dates to DateTime, add FKs & indexes Revision…, Check if the index exists, Check if a constraint exists (+2 more)

### Community 96 - "Community 96"
Cohesion: 0.20
Nodes (5): get_roles_with_max_perms(), Return roles whose permissions are a subset of max_perms (bitwise)., Role with ADMINS_MANAGE(32) should NOT appear when caller_perms=31., Role with USE+BROADCAST(3) should appear when caller_perms=31., TestBitwiseRegressions

### Community 99 - "Community 99"
Cohesion: 0.20
Nodes (4): FakeFSMContext, fsm_context(), Provide a FakeFSMContext instance., Dict-backed FSMContext replacement.

### Community 100 - "Community 100"
Cohesion: 0.31
Nodes (5): Whether any registered callback_query handler's filters accept payload., Guard against the check silently passing everything., The prefixes these views used to generate had no handler at all. Kept as a…, TestEveryNavPrefixHasAHandler, walk()

### Community 101 - "Community 101"
Cohesion: 0.24
Nodes (5): The receipt's Back button leads to the item card, whose own Back is gp_/sp_ —…, The filters aiogram will run for a handler, as registered., Whether aiogram's own filters would let this callback through. Calling the…, Guard: with the browsing state cleared, gp_0 must NOT route., TestBackFromItemCardAfterPurchase

### Community 102 - "Community 102"
Cohesion: 0.39
Nodes (6): dsn(), do_run_migrations(), get_url(), run_migrations_offline(), run_migrations_online(), run_migrations_online_async()

### Community 103 - "Community 103"
Cohesion: 0.31
Nodes (4): _build_perms_keyboard(), _format_permissions(), InlineKeyboardMarkup, TestHelpers

### Community 104 - "Community 104"
Cohesion: 0.25
Nodes (7): process_replenish_balance(), callback_query, Create an invoice for the chosen payment method., Bot, Send Telegram Stars invoice (currency='XTR', provider_token='').…, send_stars_invoice(), TestSendStarsInvoice

### Community 105 - "Community 105"
Cohesion: 0.36
Nodes (3): item_info_callback_handler(), Show detailed information about the item. Format: itm:{index}:{page}, TestItemInfo

### Community 106 - "Community 106"
Cohesion: 0.28
Nodes (6): get_role_cached(), A user's permission bitmask, cached in-process then in Redis. Three tiers,…, Cached permission bitmask, routed through the live middleware's cache. Single…, resolve_role_cached(), TestNegativeRoleCaching, counting_check_role()

### Community 107 - "Community 107"
Cohesion: 0.28
Nodes (6): BroadcastMessage, Validate broadcast message, Validate HTML tags after all fields are set, model_validator, Self, TestBroadcastMessage

### Community 108 - "Community 108"
Cohesion: 0.47
Nodes (8): iter_python_files(), main(), module_episode_body(), project_overview_body(), Path, Индексирует структуру репозитория в Graphiti (эпизоды по модулям + обзор…, repo_root(), run_index()

### Community 109 - "Community 109"
Cohesion: 0.32
Nodes (5): check_item_name_for_add(), If position already exists — inform the user; otherwise save name and ask for…, is_safe_item_name(), Check that the product name is safe for display, TestItemNameStep

### Community 110 - "Community 110"
Cohesion: 0.36
Nodes (3): BroadcastStats, parametrize, TestBroadcastStats

### Community 111 - "Community 111"
Cohesion: 0.36
Nodes (4): CategoryRequest, Validate category operations, Sanitize the category name, TestCategoryRequest

### Community 113 - "Community 113"
Cohesion: 0.52
Nodes (3): cart_keyboard(), Cart view: a quantity stepper, an optional promo-drop button, and a remove…, TestCartKeyboard

### Community 114 - "Community 114"
Cohesion: 0.29
Nodes (6): Cursor / MCP (опционально), Graphiti — граф знаний по репозиторию, Быстрый старт, Повторная индексация, Связь с MEMORY.md, Требования

### Community 115 - "Community 115"
Cohesion: 0.38
Nodes (5): _ensure_pg_trgm(), _index_exists(), add goods search indexes Revision ID: f2a3b4c5d6e7 Revises: e1f2a3b4c5d6 Create…, Install pg_trgm, returning False if we lack the privilege. CREATE EXTENSION…, upgrade()

### Community 116 - "Community 116"
Cohesion: 0.33
Nodes (4): The 6 existing call sites must be byte-identical., TestLazyPaginatedExtraRows, _query(), _kb()

### Community 118 - "Community 118"
Cohesion: 0.40
Nodes (3): True if `perms` has any permission beyond USE., parametrize, TestPermissionHelpers

### Community 120 - "Community 120"
Cohesion: 0.47
Nodes (3): Send invoice via Telegram Payments (fiat provider). `amount` is given in major…, send_fiat_invoice(), TestSendFiatInvoice

### Community 121 - "Community 121"
Cohesion: 0.47
Nodes (5): main(), Path, Гибридный поиск по графу Graphiti (CLI)., repo_root(), search()

### Community 122 - "Community 122"
Cohesion: 0.47
Nodes (4): _find_fk(), _index_exists(), Find FK constraint name by local column and optional referent table., upgrade()

### Community 123 - "Community 123"
Cohesion: 0.60
Nodes (5): downgrade(), _has_column(), _has_constraint(), Drop quantity and its constraints. Lossy by design: a row with quantity=N is…, upgrade()

### Community 126 - "Community 126"
Cohesion: 0.50
Nodes (3): check_sub(), checks the channel subscription., TestCheckSub

### Community 127 - "Community 127"
Cohesion: 0.60
Nodes (3): _column_exists(), find_fk_name_sa(), upgrade()

### Community 128 - "Community 128"
Cohesion: 0.60
Nodes (4): downgrade(), _has_check(), Drop the discriminator. Lossless for every non-dangling row: scope is derivable…, upgrade()

### Community 130 - "Community 130"
Cohesion: 0.60
Nodes (4): downgrade(), _index_names(), pagination tiebreaker indexes Revision ID: d7e8f9a0b1c2 Revises: c8d9e0f1a2b3…, upgrade()

### Community 131 - "Community 131"
Cohesion: 0.60
Nodes (3): _check_constraint_exists(), _index_exists(), upgrade()

### Community 134 - "Community 134"
Cohesion: 0.83
Nodes (3): downgrade(), _has_column(), upgrade()

### Community 135 - "Community 135"
Cohesion: 0.83
Nodes (3): downgrade(), _index_exists(), upgrade()

## Knowledge Gaps
- **43 isolated node(s):** `docker-entrypoint.sh script`, `🎬 Demo`, `📋 Table of Contents`, `✨ Features`, `🔒 Security` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 868 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Database` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 8`, `Community 9`, `Community 13`, `Community 14`, `Community 16`, `Community 18`, `Community 19`, `Community 21`, `Community 24`, `Community 25`, `Community 28`, `Community 29`, `Community 30`, `Community 32`, `Community 33`, `Community 35`, `Community 36`, `Community 41`, `Community 43`, `Community 44`, `Community 46`, `Community 47`, `Community 50`, `Community 51`, `Community 52`, `Community 55`, `Community 58`, `Community 63`, `Community 64`, `Community 69`, `Community 70`, `Community 73`, `Community 75`, `Community 76`, `Community 77`, `Community 86`, `Community 88`, `Community 89`, `Community 96`, `Community 102`, `Community 117`?**
  _High betweenness centrality (0.244) - this node is a cross-community bridge._
- **Why does `localize()` connect `Community 11` to `Community 0`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 13`, `Community 15`, `Community 17`, `Community 19`, `Community 20`, `Community 24`, `Community 29`, `Community 31`, `Community 33`, `Community 34`, `Community 35`, `Community 37`, `Community 38`, `Community 41`, `Community 43`, `Community 44`, `Community 45`, `Community 48`, `Community 49`, `Community 53`, `Community 55`, `Community 59`, `Community 60`, `Community 61`, `Community 65`, `Community 70`, `Community 71`, `Community 72`, `Community 73`, `Community 74`, `Community 78`, `Community 80`, `Community 81`, `Community 87`, `Community 89`, `Community 90`, `Community 91`, `Community 93`, `Community 103`, `Community 104`, `Community 105`, `Community 109`, `Community 113`, `Community 120`, `Community 126`?**
  _High betweenness centrality (0.185) - this node is a cross-community bridge._
- **Why does `log_audit()` connect `Community 21` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 11`, `Community 17`, `Community 18`, `Community 19`, `Community 20`, `Community 24`, `Community 29`, `Community 33`, `Community 35`, `Community 37`, `Community 38`, `Community 41`, `Community 43`, `Community 47`, `Community 48`, `Community 53`, `Community 58`, `Community 59`, `Community 64`, `Community 65`, `Community 70`, `Community 72`, `Community 78`, `Community 87`, `Community 89`, `Community 104`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 100 inferred relationships involving `Database` (e.g. with `AuditBuffer` and `clear_cart()`) actually correct?**
  _`Database` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `back()` (e.g. with `broadcast_messages()` and `send_message_callback_handler()`) actually correct?**
  _`back()` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LazyPaginator` (e.g. with `navigate_items_in_goods()` and `process_delete_item_from_position()`) actually correct?**
  _`LazyPaginator` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `docker-entrypoint.sh script`, `🎬 Demo`, `📋 Table of Contents` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._