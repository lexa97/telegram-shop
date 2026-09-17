"""workers TZ-12: delivery_notified_at, fulfillment attempts, processing_started_at

Revision ID: f2a3b4c5d6e8
Revises: e0f1a2b3c4d5
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e8"
down_revision: Union[str, None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("fulfillment_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "orders",
        sa.Column(
            "processing_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "delivery_notified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "delivery_notified_at")
    op.drop_column("orders", "processing_started_at")
    op.drop_column("orders", "fulfillment_attempt_count")
