from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config import settings

router = Router()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Используйте: /broadcast <текст>")
        return
    from aiogram import Bot
    from db.engine import async_session
    from db.models import User
    from sqlalchemy import select

    bot: Message.bot = message.bot
    async with async_session() as session:
        result = await session.execute(select(User.id))
        user_ids = [row[0] for row in result.all()]

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, parts[1])
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"Отправлено: {sent}\nОшибки: {failed}")
