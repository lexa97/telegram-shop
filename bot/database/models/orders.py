import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.main import Database


class OrderStatus:
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"

    ALL = frozenset(
        {CREATED, PROCESSING, COMPLETED, FAILED, EXPIRED, REFUNDED}
    )


class DeliveryType:
    STOCK = "STOCK"
    API = "API"
    GIFT = "GIFT"


class Order(Database.BASE):
    """Customer order with immutable financial snapshot (amounts in kopecks)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    goods_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    fee_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    referral_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    profit_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=OrderStatus.CREATED, index=True)
    delivery_type: Mapped[str] = mapped_column(String(8), nullable=False)

    provider_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    provider_external_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    fulfillment_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gift_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fulfillment_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    processing_started_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_notified_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", lazy="raise")
    goods: Mapped["Goods"] = relationship("Goods", lazy="raise")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        lazy="raise",
        order_by="OrderStatusHistory.id",
    )
    bought_goods: Mapped[list["BoughtGoods"]] = relationship(
        "BoughtGoods",
        back_populates="order",
        lazy="raise",
    )  # noqa: F821 — BoughtGoods defined in main.py

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_orders_quantity_positive"),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in sorted(OrderStatus.ALL))})",
            name="ck_orders_status",
        ),
        CheckConstraint(
            f"delivery_type IN ({', '.join(repr(t) for t in (DeliveryType.STOCK, DeliveryType.API, DeliveryType.GIFT))})",
            name="ck_orders_delivery_type",
        ),
        CheckConstraint("total_cents >= 0", name="ck_orders_total_nonneg"),
        UniqueConstraint("provider_external_order_id", name="uq_orders_provider_external_id"),
        Index("ix_orders_status_created", "status", "created_at"),
        Index("ix_orders_expires_at", "expires_at"),
    )

    def __str__(self):
        return f"Order#{self.id} {self.status}"


class OrderStatusHistory(Database.BASE):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped["Order"] = relationship("Order", back_populates="status_history", lazy="raise")

    def __str__(self):
        return f"OrderStatusHistory#{self.id} {self.from_status}->{self.to_status}"

