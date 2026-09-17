import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Integer, String, BigInteger, ForeignKey, Text, Boolean,
    DateTime, Numeric, Index, UniqueConstraint, CheckConstraint, func, select
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from bot.database.main import Database


class Permission:
    USE             = 1 << 0   #   1 — basic access
    BROADCAST       = 1 << 1   #   2 — mass messaging
    SETTINGS_MANAGE = 1 << 2   #   4 — bot settings (maintenance, etc.)
    USERS_MANAGE    = 1 << 3   #   8 — view/block/unblock users, referrals, purchases
    CATALOG_MANAGE  = 1 << 4   #  16 — categories, positions, items/goods CRUD
    ADMINS_MANAGE   = 1 << 5   #  32 — role CRUD, role assignment
    OWN             = 1 << 6   #  64 — owner-only operations
    STATS_VIEW      = 1 << 7   # 128 — statistics, logs, bought-item search
    BALANCE_MANAGE  = 1 << 8   # 256 — top-up / deduct user balance
    PROMO_MANAGE    = 1 << 9   # 512 — promo code CRUD
    TICKETS_MANAGE  = 1 << 10  # 1024 — support tickets (ТЗ-09)

    _ALL_BITS = (
        USE, BROADCAST, SETTINGS_MANAGE, USERS_MANAGE, CATALOG_MANAGE,
        ADMINS_MANAGE, OWN, STATS_VIEW, BALANCE_MANAGE, PROMO_MANAGE,
        TICKETS_MANAGE,
    )

    @staticmethod
    def all_bits() -> int:
        mask = 0
        for bit in Permission._ALL_BITS:
            mask |= bit
        return mask

    @staticmethod
    def is_subset(perms: int, of: int) -> bool:
        """True if every bit in `perms` is also set in `of`."""
        return (perms & ~of) == 0

    @staticmethod
    def has_any_admin_perm(perms: int) -> bool:
        """True if `perms` has any permission beyond USE."""
        return (perms & ~Permission.USE) != 0

    @staticmethod
    def granted(perms: int, bit: int) -> bool:
        """True if every bit in `bit` is set in `perms` (same AND semantics as HasPermissionFilter)."""
        return (perms & bit) == bit


class Role(Database.BASE):
    __tablename__ = 'roles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    default: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, index=True)
    permissions: Mapped[Optional[int]] = mapped_column(Integer)
    users: Mapped[list["User"]] = relationship('User', backref='role', lazy='raise')

    def __str__(self):
        return self.name or ""

    @staticmethod
    async def insert_roles():
        roles = {
            'USER': [Permission.USE],
            'ADMIN': [Permission.USE, Permission.BROADCAST,
                      Permission.SETTINGS_MANAGE, Permission.USERS_MANAGE,
                      Permission.CATALOG_MANAGE, Permission.STATS_VIEW,
                      Permission.BALANCE_MANAGE, Permission.PROMO_MANAGE,
                      Permission.TICKETS_MANAGE],
            'OWNER': [Permission.USE, Permission.BROADCAST,
                      Permission.SETTINGS_MANAGE, Permission.USERS_MANAGE,
                      Permission.CATALOG_MANAGE, Permission.ADMINS_MANAGE,
                      Permission.OWN, Permission.STATS_VIEW,
                      Permission.BALANCE_MANAGE, Permission.PROMO_MANAGE,
                      Permission.TICKETS_MANAGE],
        }
        default_role = 'USER'
        async with Database().session() as s:
            for r, perms in roles.items():
                result = await s.execute(select(Role).filter_by(name=r))
                role = result.scalars().first()
                if role is None:
                    role = Role(name=r)
                    s.add(role)
                role.reset_permissions()
                for perm in perms:
                    role.add_permission(perm)
                role.default = (role.name == default_role)

    def add_permission(self, perm):
        self.permissions |= perm

    def remove_permission(self, perm):
        self.permissions &= ~perm

    def reset_permissions(self):
        self.permissions = 0

    def has_permission(self, perm):
        return self.permissions & perm == perm

    def __repr__(self):
        return '<Role %r>' % self.name


class User(Database.BASE):
    __tablename__ = 'users'
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('roles.id', ondelete="RESTRICT"), default=1, index=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    referral_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    registration_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    is_blocked: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, index=True)
    user_operations: Mapped[list["Operations"]] = relationship(
        "Operations", back_populates="user_telegram_id", lazy='raise')
    user_goods: Mapped[list["BoughtGoods"]] = relationship(
        "BoughtGoods", back_populates="user_telegram_id", lazy='raise')

    __table_args__ = (
        CheckConstraint('referral_id != telegram_id', name='ck_users_no_self_referral'),
        CheckConstraint('balance >= 0', name='ck_users_balance_nonneg'),
        Index('ix_users_registration_date', 'registration_date'),
    )

    referral_earnings_received: Mapped[list["ReferralEarnings"]] = relationship(
        "ReferralEarnings",
        foreign_keys="ReferralEarnings.referrer_id",
        back_populates="referrer",
        lazy='raise',
    )
    referral_earnings_generated: Mapped[list["ReferralEarnings"]] = relationship(
        "ReferralEarnings",
        foreign_keys="ReferralEarnings.referral_id",
        back_populates="referral",
        lazy='raise',
    )

    def __str__(self):
        return str(self.telegram_id)


class Categories(Database.BASE):
    __tablename__ = 'categories'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    items: Mapped[list["Goods"]] = relationship(
        "Goods", back_populates="category", lazy='raise', passive_deletes=True)

    def __str__(self):
        return self.name or ""


class Goods(Database.BASE):
    __tablename__ = 'goods'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('categories.id', ondelete="CASCADE"), nullable=False, index=True)
    fulfillment_type: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="STOCK", default="STOCK")
    allows_gift: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)
    sale_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    sale_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    category: Mapped["Categories"] = relationship("Categories", back_populates="items", lazy='raise')
    values: Mapped[list["ItemValues"]] = relationship(
        "ItemValues", back_populates="item", lazy='raise', passive_deletes=True)

    def __str__(self):
        return self.name or ""


class ItemValues(Database.BASE):
    __tablename__ = 'item_values'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('goods.id', ondelete="CASCADE"), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_infinity: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="AVAILABLE", default="AVAILABLE")
    reserved_order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('orders.id', ondelete="SET NULL"), nullable=True, index=True)
    item: Mapped["Goods"] = relationship("Goods", back_populates="values", lazy='raise')

    __table_args__ = (
        UniqueConstraint('item_id', 'value', name='uq_item_value_per_item'),
        Index('ix_item_values_item_inf', 'item_id', 'is_infinity'),
        Index('ix_item_values_item_status', 'item_id', 'status'),
    )

    def __str__(self):
        return f"#{self.id} ({self.item_id})"


class BoughtGoods(Database.BASE):
    __tablename__ = 'bought_goods'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buyer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    bought_datetime: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    unique_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('orders.id', ondelete="SET NULL"), nullable=True, index=True)
    user_telegram_id: Mapped[Optional["User"]] = relationship(
        "User", back_populates="user_goods", lazy='raise')
    order: Mapped[Optional["Order"]] = relationship(
        "Order", back_populates="bought_goods", lazy='raise')

    __table_args__ = (
        Index('ix_bought_goods_datetime', 'bought_datetime'),
        Index('ix_bought_goods_buyer_datetime_id', 'buyer_id', 'bought_datetime', 'id'),
    )

    def __str__(self):
        return self.item_name or ""


class Operations(Database.BASE):
    __tablename__ = 'operations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    operation_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    user_telegram_id: Mapped[Optional["User"]] = relationship(
        "User", back_populates="user_operations", lazy='raise')

    __table_args__ = (
        Index('ix_operations_time', 'operation_time'),
    )

    def __str__(self):
        return f"#{self.id}"


class Payments(Database.BASE):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    internal_uuid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='uq_payment_provider_ext'),
        Index('ix_payments_status_created', 'status', 'created_at'),
    )

    def __str__(self):
        return f"{self.provider}:{self.external_id}"


class ReferralEarnings(Database.BASE):
    __tablename__ = 'referral_earnings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"), nullable=False, index=True)
    referral_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    referrer: Mapped["User"] = relationship(
        "User",
        foreign_keys="ReferralEarnings.referrer_id",
        back_populates="referral_earnings_received",
        lazy='raise',
    )
    referral: Mapped["User"] = relationship(
        "User",
        foreign_keys="ReferralEarnings.referral_id",
        back_populates="referral_earnings_generated",
        lazy='raise',
    )

    __table_args__ = (
        CheckConstraint('referrer_id != referral_id', name='ck_referral_earnings_no_self_referral'),
        Index('ix_referral_earnings_referrer_created_id', 'referrer_id', 'created_at', 'id'),
        Index('ix_referral_earnings_referral_created_id', 'referral_id', 'created_at', 'id'),
        Index('ix_referral_earnings_pair_created', 'referrer_id', 'referral_id', 'created_at', 'id'),
    )

    def __str__(self):
        return f"#{self.id}"


class AuditLog(Database.BASE):
    __tablename__ = 'audit_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    level: Mapped[str] = mapped_column(String(8), nullable=False, default="INFO")
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        Index('ix_audit_log_timestamp', 'timestamp'),
        Index('ix_audit_log_user_id', 'user_id'),
        Index('ix_audit_log_action', 'action'),
    )

    def __repr__(self):
        return f'<AuditLog {self.action} user={self.user_id} @ {self.timestamp}>'

    def __str__(self):
        return self.action or ""


class PromoCodes(Database.BASE):
    __tablename__ = 'promo_codes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    discount_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'percent' | 'fixed' | 'balance'
    discount_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, server_default='global')
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = unlimited
    max_uses_per_user: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    min_order_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    current_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('categories.id', ondelete='SET NULL'), nullable=True, index=True)
    item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('goods.id', ondelete='SET NULL'), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("scope IN ('global','category','item')", name='ck_promo_codes_scope'),
        CheckConstraint('discount_value >= 0', name='ck_promo_discount_nonneg'),
        CheckConstraint(
            'category_id IS NULL OR item_id IS NULL',
            name='ck_promo_single_binding',
        ),
        Index('ix_promo_codes_created_id', 'created_at', 'id'),
    )

    def __str__(self):
        return self.code or ""


def promo_scope_for(category_id: Optional[int], item_id: Optional[int]) -> str:
    """Derive a promo's scope discriminator from its bindings (item wins).

    Item-first matches the precedence in promo_rule_error.
    """
    if item_id is not None:
        return 'item'
    if category_id is not None:
        return 'category'
    return 'global'


class PromoCodeUsages(Database.BASE):
    __tablename__ = 'promo_code_usages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('promo_codes.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('orders.id', ondelete='SET NULL'), nullable=True, index=True
    )
    used_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class CartItems(Database.BASE):
    __tablename__ = 'cart_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('goods.id', ondelete='CASCADE'), nullable=False, index=True)
    promo_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint('user_id', 'item_id', name='uq_cart_item_per_user'),
        CheckConstraint('quantity > 0', name='ck_cart_items_quantity_positive'),
    )

    def __str__(self):
        return f"cart#{self.id} item={self.item_id} x{self.quantity}"


class Reviews(Database.BASE):
    __tablename__ = 'reviews'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('goods.id', ondelete='CASCADE'), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint('user_id', 'item_id', name='uq_review_per_user_item'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating_range'),
        Index('ix_reviews_item_created_id', 'item_id', 'created_at', 'id'),
    )

    def __str__(self):
        return f"item {self.item_id} ({self.rating}★)"


class StockSubscriptions(Database.BASE):
    __tablename__ = 'stock_subscriptions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('goods.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint('user_id', 'item_id', name='uq_stock_sub_per_user_item'),
    )

    def __str__(self):
        return f"sub u={self.user_id} item={self.item_id}"


async def register_models():
    """Seed the built-in roles (USER/ADMIN/OWNER)."""
    await Role.insert_roles()
