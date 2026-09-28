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
    from sqlalchemy import text
    from db.bootstrap import ensure_enum_statements
    from db.engine import engine, Base

    last_err: Exception | None = None
    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                for stmt in ensure_enum_statements():
                    await conn.execute(text(stmt))
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception as e:  # noqa: BLE001 - keep the process alive, retry later
            last_err = e
            logging.getLogger(__name__).warning("DB schema init attempt %s failed: %s", attempt + 1, e)
            await asyncio.sleep(5)
    logging.getLogger(__name__).warning("DB schema init failed after retries: %s", last_err)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    await on_startup()

    bot = create_bot()
    dp = create_dispatcher()

    asyncio.create_task(dp.start_polling(bot))

    port = int(os.environ.get("PORT", settings.WEBAPP_PORT))
    uv_config = uvicorn.Config(
        fastapi_app,
        host=settings.WEBAPP_HOST,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(uv_config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
