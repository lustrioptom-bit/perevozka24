#!/bin/bash
echo "Running Alembic migrations..."
alembic upgrade head 2>&1 || echo "Alembic failed, trying raw SQL..."
python -c "
from config import settings
import psycopg2
conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
conn.autocommit = True
cur = conn.cursor()
for col, typ in [('driver_lat','DOUBLE PRECISION'),('driver_lng','DOUBLE PRECISION'),('driver_location_updated_at','TIMESTAMP')]:
    cur.execute(f\"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col} {typ}\")
cur.execute('''CREATE TABLE IF NOT EXISTS route_subscriptions (
    id SERIAL PRIMARY KEY,
    route VARCHAR(64) NOT NULL,
    username VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT now()
)''')
cur.close()
conn.close()
print('Ensured driver location columns + route_subscriptions exist')
" 2>&1 || echo "Raw SQL also failed"
echo "Done!"
