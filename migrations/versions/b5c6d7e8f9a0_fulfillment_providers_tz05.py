"""fulfillment providers and goods_provider_links

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-16

"""
import json
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fulfillment_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("default_timeout_seconds", sa.Integer(), server_default="30", nullable=False),
        sa.Column("default_retry_count", sa.Integer(), server_default="3", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_fulfillment_providers_code"),
    )
    op.create_table(
        "goods_provider_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goods_id", sa.Integer(), sa.ForeignKey("goods.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "provider_id",
            sa.Integer(),
            sa.ForeignKey("fulfillment_providers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_product_id", sa.String(length=128), nullable=False),
        sa.Column("cost_cents", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("request_params", sa.Text(), server_default="{}", nullable=False),
        sa.Column("result_mapping", sa.Text(), server_default="{}", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("delivery_template", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.UniqueConstraint(
            "goods_id",
            "provider_id",
            "external_product_id",
            name="uq_goods_provider_external_product",
        ),
    )
    op.create_index("ix_goods_provider_links_goods_id", "goods_provider_links", ["goods_id"])
    op.create_index("ix_goods_provider_links_provider_id", "goods_provider_links", ["provider_id"])

    wizard_cfg = json.dumps(
        {
            "base_url": os.getenv("WIZARD_BASE_URL", "https://api.wizard.example"),
            "api_key": os.getenv("WIZARD_API_KEY", ""),
            "timeout_seconds": 30,
            "result_mapping": {"path": "delivery.value"},
        }
    )
    op.bulk_insert(
        sa.table(
            "fulfillment_providers",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("enabled", sa.Boolean),
            sa.column("config_json", sa.Text),
        ),
        [
            {"code": "wizard", "name": "Wizard", "enabled": True, "config_json": wizard_cfg},
            {"code": "fake", "name": "Fake (tests)", "enabled": False, "config_json": '{"mode":"success"}'},
        ],
    )

    op.create_foreign_key(
        "fk_orders_fulfillment_provider_id",
        "orders",
        "fulfillment_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_fulfillment_provider_id", "orders", type_="foreignkey")
    op.drop_index("ix_goods_provider_links_provider_id", table_name="goods_provider_links")
    op.drop_index("ix_goods_provider_links_goods_id", table_name="goods_provider_links")
    op.drop_table("goods_provider_links")
    op.drop_table("fulfillment_providers")
