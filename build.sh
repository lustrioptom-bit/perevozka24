#!/bin/bash
echo "Running Alembic migrations..."
alembic upgrade head 2>&1 || echo "Alembic failed, trying raw SQL..."
python -c "
from config import settings
from db.bootstrap import ensure_enum_statements
import psycopg2
conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
conn.autocommit = True
cur = conn.cursor()
for stmt in ensure_enum_statements():
    cur.execute(stmt)
for col, typ in [('driver_lat','DOUBLE PRECISION'),('driver_lng','DOUBLE PRECISION'),('driver_location_updated_at','TIMESTAMP')]:
    cur.execute(f"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col} {typ}")
for col, ddl in [
    ('phone_verified', 'BOOLEAN DEFAULT FALSE'),
    ('rating_count', 'INTEGER DEFAULT 0'),
    ("driver_level", "VARCHAR(16) DEFAULT 'novice'"),
]:
    cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {ddl}")
cur.execute("DO $$ BEGIN ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'in_transit'; EXCEPTION WHEN undefined_object THEN NULL; WHEN duplicate_object THEN NULL; END $$")
cur.execute('''CREATE TABLE IF NOT EXISTS driver_preferences (
    id SERIAL PRIMARY KEY,
    driver_id BIGINT UNIQUE REFERENCES users(id),
    order_types VARCHAR(20) DEFAULT 'both',
    cities TEXT DEFAULT '[]',
    radius_km INTEGER DEFAULT 50,
    frequency VARCHAR(16) DEFAULT 'instant',
    last_notified_at TIMESTAMP,
    notif_count_this_hour INTEGER DEFAULT 0,
    notif_hour_start TIMESTAMP,
    last_active_at TIMESTAMP
)''')
cur.execute('''CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    reviewer_id BIGINT REFERENCES users(id),
    reviewee_id BIGINT REFERENCES users(id),
    rating INTEGER NOT NULL,
    comment TEXT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT now()
)''')
cur.execute('''CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    order_id INTEGER REFERENCES orders(id),
    type VARCHAR(16) DEFAULT 'new_order',
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now()
)''')
cur.execute('''CREATE TABLE IF NOT EXISTS route_subscriptions (
    id SERIAL PRIMARY KEY,
    route VARCHAR(64) NOT NULL,
    username VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT now()
)''')
cur.close()
conn.close()
print('Ensured new columns + driver_preferences/reviews/notifications/route_subscriptions exist')
" 2>&1 || echo "Raw SQL also failed"
echo "Done!"
