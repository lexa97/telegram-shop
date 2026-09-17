"""promo min_order/max_uses_per_user; referral per order

Revision ID: c7d8e9f0a1b2
Revises: b5c6d7e8f9a0
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "promo_codes",
        sa.Column("min_order_cents", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "promo_codes",
        sa.Column("max_uses_per_user", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "promo_code_usages",
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_promo_code_usages_order_id", "promo_code_usages", ["order_id"])

    with op.batch_alter_table("promo_code_usages") as batch:
        batch.drop_constraint("uq_promo_usage_per_user", type_="unique")

    op.add_column(
        "referral_earnings",
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_referral_earnings_order_id", "referral_earnings", ["order_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_referral_earnings_order_id", table_name="referral_earnings")
    op.drop_column("referral_earnings", "order_id")

    with op.batch_alter_table("promo_code_usages") as batch:
        batch.create_unique_constraint("uq_promo_usage_per_user", ["promo_id", "user_id"])

    op.drop_index("ix_promo_code_usages_order_id", table_name="promo_code_usages")
    op.drop_column("promo_code_usages", "order_id")
    op.drop_column("promo_codes", "max_uses_per_user")
    op.drop_column("promo_codes", "min_order_cents")
