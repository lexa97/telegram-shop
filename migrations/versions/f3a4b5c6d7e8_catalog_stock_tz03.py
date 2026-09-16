"""catalog stock: goods fulfillment_type, item_values status/reservation

Revision ID: f3a4b5c6d7e8
Revises: e9f0a1b2c3d4
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goods",
        sa.Column("fulfillment_type", sa.String(length=8), server_default="STOCK", nullable=False),
    )
    op.add_column(
        "goods",
        sa.Column("allows_gift", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "item_values",
        sa.Column("status", sa.String(length=16), server_default="AVAILABLE", nullable=False),
    )
    op.add_column(
        "item_values",
        sa.Column("reserved_order_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_item_values_reserved_order_id",
        "item_values",
        "orders",
        ["reserved_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_item_values_item_status", "item_values", ["item_id", "status"], unique=False)
    op.create_index("ix_item_values_reserved_order_id", "item_values", ["reserved_order_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_item_values_reserved_order_id", table_name="item_values")
    op.drop_index("ix_item_values_item_status", table_name="item_values")
    op.drop_constraint("fk_item_values_reserved_order_id", "item_values", type_="foreignkey")
    op.drop_column("item_values", "reserved_order_id")
    op.drop_column("item_values", "status")
    op.drop_column("goods", "allows_gift")
    op.drop_column("goods", "fulfillment_type")
