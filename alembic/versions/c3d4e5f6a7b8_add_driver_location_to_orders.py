"""add driver location tracking to orders

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("driver_lat", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("driver_lng", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("driver_location_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "driver_location_updated_at")
    op.drop_column("orders", "driver_lng")
    op.drop_column("orders", "driver_lat")
