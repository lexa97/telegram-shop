"""RBAC TZ-08: SUPERADMIN rename, OPERATOR/MANAGER roles

Revision ID: d8e9f0a1b2c3
Revises: b5c6d7e8f9a0
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE roles SET name = 'SUPERADMIN' WHERE name = 'OWNER'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE roles SET name = 'OWNER' WHERE name = 'SUPERADMIN'"))
