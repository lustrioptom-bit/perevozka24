from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from sqlalchemy import select, func, or_

from db.models import User, Order, OrderType, OrderStatus, Vehicle
from bot.utils.helpers import get_or_create_user
from bot.utils.levels import get_level_info, level_progress
from bot.keyboards.inline import profile_keyboard

router = Router()

LEVEL_BADGES = {
    "novice": "Новичок",
    "verified": "Проверенный",
    "pro": "Профессионал",
    "expert": "Эксперт",
}


async def build_profile_text(session, user: User, viewer_id: int | None = None) -> str:
    role_label = "Водитель" if user.role.value == "driver" else ("Клиент" if user.role.value == "client" else "Водитель и клиент")
    name = user.full_name or user.username or f"ID {user.id}"
    lines = [f"{name} | {role_label}", ""]

    lines.append(f"⭐ {user.rating:.1f} ({user.rating_count} отзывов)")
    lines.append(f"✅ {user.deals_completed} успешных сделок")

    vehicles = (await session.execute(select(Vehicle).where(Vehicle.user_id == user.id))).scalars().all()
    for v in vehicles:
        type_label = {"car": "Авто", "minivan": "Минивэн", "truck_3_5t": "Грузовик до 3.5т", "heavy_truck": "Фура"}.get(v.type.value, v.type.value)
        lines.append(f"🚗 {v.make_model}, {type_label}, {v.license_plate}")
    if user.created_at:
        months = max(1, (datetime.utcnow() - user.created_at).days // 30)
        lines.append(f"📅 На сервисе с {user.created_at.strftime('%m.%Y')} ({months} мес.)")
    badges = []
    if user.phone_verified and user.phone:
        badges.append("🛡 Проверенный телефон")
    if badges:
        lines.append(" ".join(badges))

    lines.append("")
    lines.append("📊 Статистика:")
    cargo = (
        await session.execute(
            select(func.count(Order.id)).where(
                or_(Order.customer_id == user.id, Order.driver_id == user.id),
                Order.type == OrderType.freight,
                Order.status == OrderStatus.completed,
            )
        )
    ).scalar() or 0
    passengers = (
        await session.execute(
            select(func.count(Order.id)).where(
                or_(Order.customer_id == user.id, Order.driver_id == user.id),
                Order.type == OrderType.passenger,
                Order.status == OrderStatus.completed,
            )
        )
    ).scalar() or 0
    cancelled = (
        await session.execute(
            select(func.count(Order.id)).where(
                or_(Order.customer_id == user.id, Order.driver_id == user.id),
                Order.status == OrderStatus.cancelled,
            )
        )
    ).scalar() or 0
    lines.append(f"• Грузов перевезено: {cargo}")
    lines.append(f"• Пассажиров перевезено: {passengers}")
    lines.append(f"• Отмененных сделок: {cancelled}")
    lines.append(f"• Средний рейтинг: {user.rating:.1f}")

    if user.role.value != "client":
        cur, nxt = get_level_info(user.deals_completed)
        if cur:
            lines.append("")
            lines.append(f"{cur['icon']} Уровень: {cur['name']}")
            lines.append(f"Бонус уровня: {cur['bonus']}")
        if nxt:
            lines.append(level_progress(user.deals_completed))
            lines.append(f"До уровня \"{nxt['name']}\" осталось {max(0, nxt['threshold'] - user.deals_completed)} сделок!")

    return "\n".join(lines)


@router.message(Command("profile"))
@router.message(Command("me"))
async def cmd_profile(message: Message, session):
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = await build_profile_text(session, user)
    await message.answer(text, reply_markup=profile_keyboard(user, self_view=True))