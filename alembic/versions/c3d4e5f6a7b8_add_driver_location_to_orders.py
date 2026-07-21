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
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS driver_lat DOUBLE PRECISION")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS driver_lng DOUBLE PRECISION")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS driver_location_updated_at TIMESTAMP")


def downgrade() -> None:
    op.drop_column("orders", "driver_location_updated_at")
    op.drop_column("orders", "driver_lng")
    op.drop_column("orders", "driver_lat")
