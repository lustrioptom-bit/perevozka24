import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from aiogram import Bot

from config import settings
from bot.setup import create_bot, create_dispatcher
from webapp.app import app as fastapi_app
from db.engine import engine, Base


async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    await on_startup()

    bot = create_bot()
    dp = create_dispatcher()

    asyncio.create_task(dp.start_polling(bot))

    uv_config = uvicorn.Config(
        fastapi_app,
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        log_level="info",
    )
    server = uvicorn.Server(uv_config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
