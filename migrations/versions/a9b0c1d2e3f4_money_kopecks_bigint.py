"""money columns: Numeric rubles -> BIGINT kopecks

Revision ID: a9b0c1d2e3f4
Revises: d7e8f9a0b1c2
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MONEY_COLUMNS = (
    ("users", "balance"),
    ("goods", "price"),
    ("bought_goods", "price"),
    ("operations", "operation_value"),
    ("payments", "amount"),
    ("referral_earnings", "amount"),
    ("referral_earnings", "original_amount"),
)


def _assert_whole_rubles(conn, table: str, column: str) -> None:
    """Fail migration if any row has fractional kopecks in Numeric(12,2)."""
    row = conn.execute(
        sa.text(
            f"SELECT 1 FROM {table} WHERE ({column} * 100) % 1 != 0 LIMIT 1"
        )
    ).first()
    if row:
        raise RuntimeError(
            f"{table}.{column} has values that are not whole kopecks at 2dp; fix data before migrating"
        )


def upgrade() -> None:
    conn = op.get_bind()
    for table, column in _MONEY_COLUMNS:
        _assert_whole_rubles(conn, table, column)

    for table, column in _MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.BigInteger(),
            postgresql_using=f"(({column} * 100)::bigint)",
        )

    # promo: percent stays as percent integer; fixed/balance become kopecks
    op.execute(
        sa.text(
            """
            UPDATE promo_codes
            SET discount_value = (discount_value * 100)::bigint
            WHERE discount_type IN ('fixed', 'balance')
            """
        )
    )
    op.alter_column(
        "promo_codes",
        "discount_value",
        type_=sa.BigInteger(),
        postgresql_using="discount_value::bigint",
    )

    op.create_check_constraint(
        "ck_users_balance_nonneg",
        "users",
        "balance >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_balance_nonneg", "users", type_="check")

    op.alter_column(
        "promo_codes",
        "discount_value",
        type_=sa.Numeric(12, 2),
        postgresql_using="discount_value::numeric(12,2)",
    )
    op.execute(
        sa.text(
            """
            UPDATE promo_codes
            SET discount_value = discount_value / 100.0
            WHERE discount_type IN ('fixed', 'balance')
            """
        )
    )

    for table, column in reversed(_MONEY_COLUMNS):
        op.alter_column(
            table,
            column,
            type_=sa.Numeric(12, 2),
            postgresql_using=f"({column}::numeric / 100)",
        )
