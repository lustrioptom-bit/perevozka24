from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import settings
from bot.handlers import common, admin
from bot.middlewares.db import DatabaseMiddleware


def create_bot() -> Bot:
    return Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.include_router(common.router)
    dp.include_router(admin.router)
    return dp
