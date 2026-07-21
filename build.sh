#!/bin/bash
echo "Running Alembic migrations..."
alembic upgrade head 2>&1 || echo "Alembic failed, trying raw SQL..."
python -c "
import psycopg2, os
db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith('postgresql+asyncpg://'):
    db_url = 'postgresql://' + db_url[len('postgresql+asyncpg://'):]
elif db_url.startswith('postgresql+psycopg://'):
    db_url = 'postgresql://' + db_url[len('postgresql+psycopg://'):]
conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()
for col, typ in [('driver_lat','DOUBLE PRECISION'),('driver_lng','DOUBLE PRECISION'),('driver_location_updated_at','TIMESTAMP')]:
    cur.execute(f\"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col} {typ}\")
cur.close()
conn.close()
print('Ensured driver location columns exist')
" 2>&1 || echo "Raw SQL also failed"
echo "Done!"
