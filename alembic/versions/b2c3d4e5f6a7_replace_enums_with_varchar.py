"""replace orderstatus enum with varchar

Revision ID: b2c3d4e5f6a7
Revises: 5c4ce6d4334d
Create Date: 2026-07-21 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '5c4ce6d4334d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE orders ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
    op.execute("ALTER TABLE bids ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text")


def downgrade() -> None:
    pass
