from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import async_session
from db.models import DriverPreference


class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            result = await handler(event, data)
            try:
                uid = None
                if isinstance(event, Message) and event.from_user:
                    uid = event.from_user.id
                elif isinstance(event, CallbackQuery) and event.from_user:
                    uid = event.from_user.id
                if uid is not None:
                    pref = (
                        await session.execute(
                            select(DriverPreference).where(DriverPreference.driver_id == uid)
                        )
                    ).scalar_one_or_none()
                    if pref:
                        from datetime import datetime
                        pref.last_active_at = datetime.utcnow()
                        await session.commit()
            except Exception:
                pass
            return result