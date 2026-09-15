"""add orders and order_status_history, bought_goods.order_id

Revision ID: e9f0a1b2c3d4
Revises: d7e8f9a0b1c2
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORDER_STATUSES = ("CREATED", "PROCESSING", "COMPLETED", "FAILED", "EXPIRED", "REFUNDED")
_DELIVERY_TYPES = ("STOCK", "API", "GIFT")


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("goods_id", sa.Integer(), sa.ForeignKey("goods.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("discount_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.BigInteger(), nullable=False),
        sa.Column("cost_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("fee_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("referral_amount_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("profit_cents", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="CREATED"),
        sa.Column("delivery_type", sa.String(8), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("provider_external_order_id", sa.String(128), nullable=True),
        sa.Column("fulfillment_payload", sa.Text(), nullable=True),
        sa.Column("gift_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_orders_quantity_positive"),
        sa.CheckConstraint(
            "status IN ('CREATED', 'PROCESSING', 'COMPLETED', 'FAILED', 'EXPIRED', 'REFUNDED')",
            name="ck_orders_status",
        ),
        sa.CheckConstraint(
            "delivery_type IN ('STOCK', 'API', 'GIFT')",
            name="ck_orders_delivery_type",
        ),
        sa.CheckConstraint("total_cents >= 0", name="ck_orders_total_nonneg"),
        sa.UniqueConstraint("provider_external_order_id", name="uq_orders_provider_external_id"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_goods_id", "orders", ["goods_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])
    op.create_index("ix_orders_expires_at", "orders", ["expires_at"])

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_order_status_history_order_id", "order_status_history", ["order_id"])

    op.add_column(
        "bought_goods",
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_bought_goods_order_id", "bought_goods", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_bought_goods_order_id", table_name="bought_goods")
    op.drop_column("bought_goods", "order_id")
    op.drop_index("ix_order_status_history_order_id", table_name="order_status_history")
    op.drop_table("order_status_history")
    op.drop_index("ix_orders_expires_at", table_name="orders")
    op.drop_index("ix_orders_status_created", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_goods_id", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")
