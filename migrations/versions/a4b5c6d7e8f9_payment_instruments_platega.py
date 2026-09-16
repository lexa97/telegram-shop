"""payment gateways, instruments, platega; payments.internal_uuid

Revision ID: a4b5c6d7e8f9
Revises: e9f0a1b2c3d4
Create Date: 2026-09-16

"""
import json
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _platega_config() -> str:
    return json.dumps(
        {
            "merchant_id": os.getenv("PLATEGA_MERCHANT_ID", ""),
            "api_secret": os.getenv("PLATEGA_SECRET", ""),
            "payment_method": int(os.getenv("PLATEGA_PAYMENT_METHOD", "11")),
            "base_url": os.getenv("PLATEGA_BASE_URL", "https://app.platega.io"),
            "return_url": os.getenv("PLATEGA_RETURN_URL", "https://t.me"),
            "failed_url": os.getenv("PLATEGA_FAILED_URL", "https://t.me"),
        }
    )


def upgrade() -> None:
    op.create_table(
        "payment_gateways",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_payment_gateways_code"),
    )
    op.create_table(
        "payment_instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="RUB", nullable=False),
        sa.Column("gateway_id", sa.Integer(), sa.ForeignKey("payment_gateways.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("code", name="uq_payment_instruments_code"),
    )
    op.create_index("ix_payment_instruments_gateway_id", "payment_instruments", ["gateway_id"])

    op.add_column("payments", sa.Column("internal_uuid", sa.String(length=36), nullable=True))
    op.create_index("ix_payments_internal_uuid", "payments", ["internal_uuid"], unique=True)

    gw = sa.table(
        "payment_gateways",
        sa.column("code", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("config_json", sa.Text),
    )
    op.bulk_insert(
        gw,
        [
            {"code": "platega", "enabled": True, "config_json": _platega_config()},
            {"code": "cryptopay", "enabled": True, "config_json": "{}"},
            {"code": "stars", "enabled": True, "config_json": "{}"},
            {"code": "telegram_fiat", "enabled": True, "config_json": "{}"},
            {"code": "heleket", "enabled": False, "config_json": "{}"},
        ],
    )

    conn = op.get_bind()
    ids = {row[0]: row[1] for row in conn.execute(sa.text("SELECT code, id FROM payment_gateways")).fetchall()}

    inst = sa.table(
        "payment_instruments",
        sa.column("code", sa.String),
        sa.column("title", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("sort_order", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("gateway_id", sa.Integer),
    )
    op.bulk_insert(
        inst,
        [
            {
                "code": "card_mir",
                "title": "Карта / МИР",
                "enabled": bool(os.getenv("PLATEGA_MERCHANT_ID") and os.getenv("PLATEGA_SECRET")),
                "sort_order": 10,
                "currency": "RUB",
                "gateway_id": ids["platega"],
            },
            {
                "code": "cryptopay",
                "title": "CryptoPay",
                "enabled": bool(os.getenv("CRYPTO_PAY_TOKEN")),
                "sort_order": 20,
                "currency": "RUB",
                "gateway_id": ids["cryptopay"],
            },
            {
                "code": "stars",
                "title": "Telegram Stars",
                "enabled": float(os.getenv("STARS_PER_VALUE", "0") or 0) > 0,
                "sort_order": 30,
                "currency": "RUB",
                "gateway_id": ids["stars"],
            },
            {
                "code": "telegram_fiat",
                "title": "Telegram Payments",
                "enabled": bool(os.getenv("TELEGRAM_PROVIDER_TOKEN")),
                "sort_order": 40,
                "currency": "RUB",
                "gateway_id": ids["telegram_fiat"],
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_internal_uuid", table_name="payments")
    op.drop_column("payments", "internal_uuid")
    op.drop_index("ix_payment_instruments_gateway_id", table_name="payment_instruments")
    op.drop_table("payment_instruments")
    op.drop_table("payment_gateways")
