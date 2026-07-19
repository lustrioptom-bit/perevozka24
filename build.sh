#!/bin/bash
echo "Running Alembic migrations..."
alembic upgrade head 2>/dev/null || python -c "
import asyncio
from db.engine import engine, Base
from db.models import *
async def create():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(create())
print('Tables created via SQLAlchemy')
"
echo "Done!"
