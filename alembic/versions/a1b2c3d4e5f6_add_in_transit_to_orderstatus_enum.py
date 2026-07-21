"""add in_transit to orderstatus enum (superseded by varchar migration)

Revision ID: a1b2c3d4e5f6
Revises: 5c4ce6d4334d
Create Date: 2026-07-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5c4ce6d4334d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
